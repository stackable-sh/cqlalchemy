import os
import uuid
import warnings
import traceback
from datetime import datetime
from typing import Union, List, Tuple
from concurrent.futures import ThreadPoolExecutor, Future

import black

from cqlalchemy.options import keyspace
from cqlalchemy.time import minutes
from cqlalchemy.core.models import options, CqlProperty, Key
from cqlalchemy.core.builtins import fields
from cqlalchemy.connection.table import Schema, Metadata
from cqlalchemy.revisions import Project, Revision, State
from cqlalchemy.revisions.operations import Table
from cqlalchemy.revisions.templates import new_empty_file, new_project, new_migration

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

    def execute(self, project: Project):
        raise NotImplementedError("Implemented in subclasses")

"""
Initialize:
This command creates a new Revision Project in the current directory.
"""
class Initialize(Command):
    """Creates a new Revision Project"""

    def execute(self, project: Project):
        if project.exists() and project.valid():
            print("Another Revision Project already exists in this directory")
        else:
            print("Initializing new Cassandra Schema Revision Project")
            root =  os.path.join(os.getcwd(), project.root)
            if not os.path.exists(root):
                print("Creating Directory: %s" % root)
                os.mkdir(root)
            for name in project.required:
                path = os.path.join(root, name)
                if not os.path.exists(path):
                    print("Creating File: %s" % path)
                    if name in project.dirs:
                        os.mkdir(path)
                    else:
                        with open(path, "w") as f:
                            if name == "project.py":
                                f.write(new_project)
                            else:
                                f.write(new_empty_file)


"""
Sync:

This command syncs all the entities in your project to the database without generating
any migration files, which is useful for development. 
"""
class Sync(Command):
    """Makes sure that the database has all the fields that exist in your entity"""

    def execute(self, project: Project):
        """Syncs the schema to the database"""
        if not project.valid():
            raise MigrationException(f"Project: {project} is not valid")
        project.connect()
        project.setup()
        entities = set(project.entities())
        print(f"Synchronizing the schema for entities: {entities}")
        for entity in entities:
            print("Syncing: %s" % entity)
            Schema.create(entity)

"""
New:

This command creates a new database revision, which you may have to edit, 
then run, to effect a data migration or schema migration to C*

"""
class New(Command):
    """Creates a new database revision"""

    def process(self, entity: "Entity") -> List["Operation"]:
        """Handles workflow for @entity"""
        operations = []
        keyspaces = set()
        # 1. Check if the keyspace for the entity exists. 
        location = entity.keyspace()
        metadata = Metadata.fetch(keyspace=location)
        if location not in metadata.keyspaces:
            if location not in keyspaces:
                op = Keyspace(name=location)
                operations.append(op)
                keyspaces.add(location)
        # 2. Check for the Table, and Columns.
        tables = metadata.keyspaces.get(location, {})
        table = entity.table()
        if table not in tables: 
            # Create Table using default and settings. 
            op = self.table(entity, metadata=metadata)
            operations.append(op)
        else:
            # Table already exists, generate column operations. 
            ops = self.columns(entity, metadata=metadata)
            operations.extend(ops)
            ops = self.indexes(entity, metadata=metadata)
            operations.extend(ops)
        return operations
    
    def keys(self, entity: "Entity") -> Union[str, List[str]]:
        """Returns python data structure for creating key section of Table"""
        instance = Key.create(entity)
        key: Union[str, List[str]] = None 
        if instance.composite:
            start = tuple([part for part in instance.parts if part in instance.composite])
            others = [part for part in instance.parts if part not in instance.composite]
            if not others:
                key = start
            else:
                key = [start, ] + others
        else:
            key = instance.parts
        return key
    
    def order(self, entity: "Entity") -> List[Tuple[str, str]]:
        """Generate ops for creating clustering order section of Table"""
        # Generate Clustering Order
        key = Key.create(entity)
        properties = fields(entity, CqlProperty)
        cluster = []
        if key.cluster:
            for name in key.cluster:
                attribute = properties.get(name)
                if attribute.order:
                    order = (name, attribute.order)
                    cluster.append(order)
        return cluster
    
    def statics(self, entity: "Entity"):
        static = []
        properties = fields(entity, CqlProperty)
        for name, prop in properties.items():
            if prop.static:
                static.append(name)
        return static

    def table(self, entity: "Entity", metadata: Metadata) -> "Operation":
        """Generate ops for creating a table"""
        ttl = options(entity, "expire", 0)
        accord = options(entity, "accord", True)    # Accord is enabled by default.
        doc = entity.__doc__ if entity.__doc__ else ""

        columns = []
        properties = fields(entity, CqlProperty)
        for name, prop in properties.items():
            columns.append((name, prop.ctype))

        op = Table(
            keyspace=entity.keyspace(),
            name=entity.table(),
            key=self.keys(entity),
            columns=columns,
            order=self.order(entity),
            static=self.statics(entity),
            accord=accord,
            expires=ttl,
            comment=doc,
        ) 
        return op 

    def indexes(self, entity: "Entity", metadata: Metadata) -> List["Operation"]:
        """Generate ops for creating/dropping indexes"""
        keyspace = entity.keyspace()
        properties = fields(entity, CqlProperty) 
        tables = metadata.indexes.get(keyspace, {})
        if entity.table() in tables:
            ops = []
            indexes = tables[entity.table()]
            combined = set()
            for prop in properties:
                # Technical Note: We do not remove any existing indexes on the table 
                # automatically (so that we don't break any custom indexes you create for your project),
                # drop indexes manually, if you need it.
                index = Index.name(entity.table(), prop.name) 
                if prop.index and index not in indexes:
                    op = Index(
                        keyspace=keyspace,
                        table=entity.table(),
                        name=prop.name,
                        columns=[prop.name]
                    )
                    ops.append(op)
            return ops
        else:
            raise ValueError(f"Table {entity.table()} does not exist in keyspace")
            
    def columns(self, entity: "Entity", metadata: Metadata) -> List["Operation"]:
        """Generate ops for creating/dropping columns"""
        keyspace = entity.keyspace()
        properties = fields(entity, CqlProperty) 
        tables = metadata.keyspaces.get(keyspace, {})
        if entity.table() in tables:
            combined = set()
            schema = tables[entity.table()]
            for name, prop in properties.items():
                combined.add(name)
            for name in schema:
                combined.add(name)
            ops = []
            statics = self.statics(entity)
            for name in combined:
                if name in properties:
                    prop = properties[name]
                    if name not in schema:
                        static = True if name in statics else False
                        ops.append(
                            Column(
                                keyspace=keyspace,
                                table=entity.table(),
                                name=name,
                                type=prop.ctype,
                                static=static
                            )
                        )
                else:
                    ops.append(
                        Drop(
                            keyspace=keyspace,
                            table=entity.table(),
                            column=name
                        )
                    )
            return ops    
        else:
            raise ValueError(f"Table {entity.table()} does not exist in keyspace")

    def execute(self, project: Project):
        """Generates a new migration that uses your entities as the source of truth"""
        from cqlalchemy.revisions.operations import (Keyspace, Table, Column, Index, Drop)
        
        if not project.valid():
            raise MigrationException(f"Project: {project} is not valid")
        
        project.connect()
        project.setup()
            
        message = self.context.get("message", "")
        create = self.context.get("create", False)
        revision_id = str(uuid.uuid4())
        filename = project.name(revision_id, message)
        path = project.base() / filename

        operations = []
        if create:
            entities = project.entities()
            keyspaces = set()
            for entity in entities:
                ops = self.process(entity())
                operations.extend(ops)
        output = new_migration.format(
            revision=revision_id,
            message=message,
            operations=operations
        )
        formatted = black.format_str(output, mode=black.Mode(line_length=88))
        with open(path, 'w') as out:
            out.write(formatted)


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

    def execute(self, env: Project):
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
Stamp :
This command marks a particular migration as successful, allowing the migration system to skip
it and move to the next migration. 
"""

class Stamp(Command):
    """Marks a particular Migration as successful in C*"""

    def execute(self, env: Project):
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
Head:
Finds and prints the most recently applied Revision/Migration to the terminal 
"""
class Head(Command):
    """Prints the most recently applied Revision to the terminal"""

    def execute(self, env: Project):
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
Reset:
This command removes all the Migration/Revisions stored in C*, allowing you to
apply migrations afresh to C*

"""
class Reset(Command):
    """Implements the `reset` command, which removes the project keyspace from C*"""
    
    def execute(self, env: Project):
        space = keyspace()
        destroy = Confirm.ask(f"[bold red]Are you sure you want to destroy {space}: [bold red]")
        if destroy:
            print("[bold red]Removing Keyspace: %s[bold red]" % space)
            Schema.destroy(keyspace=space)
            print("[bold red]Schema successfully destroyed[bold red]")



"""
History:
Prints all Migrations/Revision along with their status to the terminal in 
a tabular format.
"""
class History(Command):
    """Prints all the attempted migrations in a tabular format to the console"""

    def execute(self, env: Project):
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
Baseline:

This command fast forwards our database migration state/records 
to a specification revision (the 'baseline') without running all the migrations 
required to get there; which is equivalent to use the Stamp command on all revisions
along the way to our baseline.

This command is useful for starting to manage a pre-existing datastore 
without recreating it from scratch. 
"""
class Baseline(Command):
    """Forwards the database to a"""

    def execute(self, env: Project):
        entities = env.entities()
        for entity in entities:
            print("Syncing: %s" % entity)
            Schema.create(entity)
        

