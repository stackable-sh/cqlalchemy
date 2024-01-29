
import os
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future

from rich import print
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from cqlalchemy.options import keyspace
from cqlalchemy.time import minutes
from cqlalchemy.core.models import options
from cqlalchemy.connection.table import Schema, Metadata
from cqlalchemy.migrate import EnvironmentContext, Revision, State
from cqlalchemy.migrate.templates import new_empty_file, new_env


terminal = Console()
executor = ThreadPoolExecutor(max_workers=1)


class Runnable(object):
    """Runs a migration in a shared single threaded"""

    def __init__(self, migration, idempotent, retry, duration) -> None:
        self.idempotent = idempotent
        self.retry = retry 
        self.duration = duration 
        self.migration = migration 
        self.stop = False 
    
    def run(self):
        """Sequentially executes the operations in a migration"""
        try:
            self.migration.prepare()
            repeat, count = 0, 0
            if self.idempotent:
                repeat = self.retry if self.retry else 1 
            while True:
                if count == repeat or self.stop:
                    break 
                else:
                    print(f"[bold green]{count} Retrying Migration: %s" % self.migration)

                self.migration.before()
                operations = self.migration.actions
                if operations:
                    for operation in operations:
                        operation.execute()
                self.migration.after()
                count += 1
            self.migration.shutdown()
            return True 
        except Exception:
            traceback.print_exc()
            return False 

    def schedule(self) -> Future:
        """Puts this runnable on the thread pool and returns a Future for tracking it"""
        future = executor.submit(self.run)
        return future



class Command(object):
    """Base class for all commands"""

    def __init__(self, **keywords):
        self.context = keywords

    def execute(self, env: EnvironmentContext):
        raise NotImplementedError("Implemented in subclasses")


class Initialize(Command):
    """Creates a new Revision Project"""

    def execute(self, env: EnvironmentContext):
        if env.exists():
            print("Another Revision Project already exists in this directory")
        else:
            root =  os.path.join(os.getcwd(), env.root)
            if not os.path.exists(root):
                print("Creating Directory: %s" % root)
                os.mkdir(root)
            for name in env.required:
                path = os.path.join(root, name)
                if not os.path.exists(path):
                    print("Creating File: %s" % path)
                    if name in env.dirs:
                        os.mkdir(path)
                    else:
                        with open(path, "w") as f:
                            if name == "env.py":
                                f.write(new_env)
                            elif name == "README":
                                f.write(self.context.get("description", ""))
                            else:
                                f.write(new_empty_file)


"""
Stamp :
This command marks a particular migration as successful, allowing the migration system to skip
it and move to the next migration. 
"""

class Stamp(Command):
    """Marks a particular Migration as successful in C*"""

    def execute(self, env: EnvironmentContext):
        revision = self.context.get("revision", "")
        if not revision:
            print("Please provide a database revision to search for.")
    
        record = Revision.read(revision)
        if record:
            record.state = State.SUCCEEDED
            record.save()
            print("[bold blue]Database Revision successfully changed[bold blue]")
        else:
            print("[bold blue]No Revision Found For: {revision}[bold blue]")
        return super().execute(env)


"""
Reset:
This command removes all the Migration/Revisions stored in C*, allowing you to
apply migrations afresh to C*

"""
class Reset(Command):
    """Implements the `reset` command, which removes the project keyspace from C*"""
    
    def execute(self, env: EnvironmentContext):
        space = keyspace()
        destroy = Confirm.ask(f"[bold red]Are you sure you want to destroy {space}: [bold red]")
        if destroy:
            print("[bold red]Removing Keyspace: %s[bold red]" % space)
            Schema.destroy(keyspace=space)
            print("[bold red]Schema successfully destroyed[bold red]")
    

"""
Head:
Finds and prints the most recently applied Revision/Migration to the terminal 
"""
class Head(Command):
    """Prints the most recently applied Revision to the terminal"""

    def execute(self, env: EnvironmentContext):
        query = Revision.objects.where(state=State.SUCCEEDED)
        revisions = query.all()
        revisions = sorted(revisions, key=lambda r: r.completed)
        if revisions:
            r = revisions[len[revisions] - 1]
            table = Table(title="Database Revisions")
            table.add_column("Completion Date", justify="center", style="bold blue")
            table.add_column("Path", justify="left", style="bold blue")
            table.add_column("Revision", justify="center", style="bold blue")
            table.add_column("Status", justify="center", style="bold blue")
            table.add_column("Checksum", justify="left", style="bold blue")
            table.add_row(r.compeleted, r.path, r.id, r.state, r.checksum)
            terminal.print(table)
        else:
            print("[bold blue]No Database Revisions Found.[bold blue]")



"""
History:
Prints all Migrations/Revision along with their status to the terminal in 
a tabular format.
"""
class History(Command):
    """Prints all the attempted migrations in a tabular format to the console"""

    def execute(self, env: EnvironmentContext):
        revisions = Revision.objects.all()
        revisions = sorted(revisions, key=lambda r: r.completed)
        if revisions:
            table = Table(title="Database Revisions")

            table.add_column("Completion Date", justify="center", style="bold blue")
            table.add_column("Path", justify="left", style="bold blue")
            table.add_column("Revision", justify="center", style="bold blue")
            table.add_column("Status", justify="center", style="bold blue")
            table.add_column("Checksum", justify="left", style="bold blue")
            for r in revisions:
                table.add_row(r.compeleted, r.path, r.id, r.state, r.checksum)
            terminal.print(table)
        else:
            print("[bold blue]No Database Revisions Found.[bold blue]")


"""
Migrate:

This command takes a directory of migration files, sorts them topologically, finds & validates their 
accompanying data models from Cassandra, (then can optionally) sequentially run all the migrations 
that have not been applied as of yet (until it reaches the HEAD or a user defined stoppage point) - 
retrying any failed steps a (configurable) number of times before giving up.

We can also generate new empty migration stubs for you to edit manually, or auto 
generate migrations from inspecting the C* Schema.
"""
class Migrate(Command):
    """Executes and applies any unapplied migration, bringing the database to date"""

    def execute(self, env: EnvironmentContext):
        stop = self.context.get("stop", "")
        migrations = env.migrations()
        records = {}
        executed_migrations, skipped_migrations = set(), set()

        print("[bold green]Starting Migration[bold green]")
        if stop:
            print(f"[bold green]Stop Point Set At: {stop}[bold green]")

        for migration in migrations:
            # Runs each migration sequentially, and in lexical order. 
            result = False
            record = migration.get(create=True)
            # Check whether another migration is running somewhere else on the infrastructure.
            if record.running:
                print("[bold red]Another CQLAlchemy migration seems to be already running against your C* cluster[bold red]")
                print("[bold red]Stopping Migration[bold red]")
                return 
            # Check if the migration script has changed since the last run
            if record.checksum != migration.checksum:
                print("[bold red]Your migration script seems to have changed since the last run")
                approval = Confirm.ask("[bold red]Do you want to run it again ('yes' or 'no')[bold red]", choices=["yes", "no"])
                if not approval:
                    print("[bold red]Skipping Migration: %s[bold red]" % migration.revision)
                    continue 
                else:
                    record.state = State.INITIALIZED
            if record.state == State.SUCCEEDED:
                print("[bold red]This migration has been applied before, skipping it.[bold red]")
                continue 
            # At this point, we should only have a new or unapplied migration. 
            # We now try to execute the migration
            try:
                # Update global state to RUNNING so that other concurrent migrations against our database will fail
                idempotent = options(migration, "idempotent", False)
                retry = options(migration, "retry", False)
                duration = options(migration, "duration", minutes(1))
                record.current = record 
                record.running = True 
                record.state = State.RUNNING
                record.save()

                # Attempt to run the migration 
                runner = Runnable(migration, idempotent, retry, duration)
                future = runner.schedule()
                result = future.result(duration)
            except TimeoutError:
                # If we get a timeout, do not interrupt the migration
                # Instead ask the migration to stop itself after the current run, 
                # then wait indefinitely for it complete.
                print("[bold red]Warning: Your migration has surpassed set duration of: {duration} seconds[bold red]")
                runner.stop = True 
                result = future.result()
            except Exception:
                traceback.print_exc()
            finally:
                # Update state so that other migrations can proceed
                record.state = State.SUCCEEDED if result else State.FAILED
                record.completed = datetime.now()
                record.running = False  
                record.save()
                executed_migrations.add(migration)
                records[migration.revision] = record

            # Check if this is the migration that we are supposed to stop at
            if stop and stop == migration.revision:
                print("[bold green]Stopping Migration At: %s" % migration.revision)
                break
        
        # Check if all the migrations ran, and update the state of the ones that we skipped
        if len(executed_migrations) != len(migrations):
            for migration in migrations:
                if migration not in executed_migrations:
                    record = migration.get(create=True)
                    record.state = State.SKIPPED
                    record.save()
                    skipped_migrations.add(migration)
                    records[migration.revision] = record 

        table = Table(title="Migration Status")
        table.add_column("Path", justify="left", style="bold blue")
        table.add_column("Revision", justify="left", style="bold blue")
        table.add_column("Status", justify="left", style="bold blue")
        table.add_column("Checksum", justify="left", style="bold blue")
        for m in migrations:
            record = records[migration.revision]
            table.add_row(m.path, m.revision, record.state, record.checksum)
        terminal.print(table)
            


"""
New:

This command creates a new database revision, which you may have to edit, 
then run, to effect a data migration or schema migration to C*

TODO: Implement the `new` command
"""
class New(Command):
    """Creates a new database revision"""

    def execute(self, env: EnvironmentContext):
        from cqlalchemy.migrate.operations import (Keyspace, Table, Column, Index, Drop)
        message = self.context.get("message", "")
        location = self.context.get("keyspace", keyspace())
        reverse = self.context.get("reverse", "")

        # TODO : Create the revision number, migration_file_name, 
        # TODO: Initialize the migration templates

        operations = []
        location = location.lower()
        if reverse:
            # Generate a forward migration that reverses the last migration
            pass
        else:
            # Generates a new migration that reflects the current state of your models in comparison with the database
            # If there haven't been any changes to your model, then simply generate a new empty migration that the developer can edit.
            
            metadata = Metadata.fetch(keyspace=location)
            
            # Check for the Keyspace
            if location not in metadata.keyspaces:
                op = Keyspace(name=location)
                operations.append(op)

            # Check for Tables
            entities = env.entities()
            for entity in entities:
                # If Table doesn't exist, create the table/columns/indexes using one bulk Table operation
                if entity.table() not in metadata.keyspaces.get(location):
                    table = Table(

                    )
                else:
                    # If Table exists, create all the columns/indexes that exist on the Entity but not in C*
                    # Then Drop all the columns/indexes that exist on C* but not on the Entity
                    pass 
        
        # Serialize the operations to a str using repr, then use it to fill up the new template
        # Write the new template to disk as a new migration in the versions folder. 
       

"""
Sync:

This command syncs all the entities in your project to the database without generating
any migration files, which is useful for development. 
"""
class Sync(Command):
    """Makes sure that the database has all the fields that exist in your entity"""

    def execute(self, env: EnvironmentContext):
        entities = env.entities()
        for entity in entities:
            print("Syncing: %s" % entity)
            Schema.create(entity)


"""
Baseline:

This command fast forwards our database migration state/records to a specification revision (the 'baseline') without 
running all the migrations required to get there; which is equivalent to use the Stamp command on all revisions
along the way to our baseline.

This command is useful for starting to manage a pre-existing datastore without recreating it from scratch. 
"""
class Baseline(Command):
    """Forwards the database to a"""

    def execute(self, env: EnvironmentContext):
        entities = env.entities()
        for entity in entities:
            print("Syncing: %s" % entity)
            Schema.create(entity)
        