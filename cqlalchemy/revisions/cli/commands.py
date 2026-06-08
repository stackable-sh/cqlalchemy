import os
import traceback
from datetime import datetime
from typing import Set, List, Tuple, Iterable

import black
import uuid_utils.compat as uuid
from rich import print
from rich.console import Console
from rich.prompt import Confirm

from cqlalchemy.options import keyspace, debug, verbose
from cqlalchemy.time import minutes
from cqlalchemy.exceptions import BaseException
from cqlalchemy.connection.cql import Atom
from cqlalchemy.core.models import options, CqlProperty, Entity
from cqlalchemy.core.builtins import fields
from cqlalchemy.connection.table import Schema, Metadata
from cqlalchemy.revisions import Project, Revision, State, Lock, Migration, MigrationException
from cqlalchemy.revisions.operations import Keyspace, Table, Column, Drop, Index, Field, Operation
from cqlalchemy.revisions.templates import new_empty_file, new_project, new_migration


class CommandException(BaseException):
    """Base Exception for all Command related exceptions"""
    pass 

class RevisionChecksumException(CommandException):
    """Raised when the checksum of a migration file has changed"""
    checksum: str 

class RevisionAppliedException(CommandException):
    """Raised when a revision that has already been applied is run again"""
    revision: str 
    
class MigrationCompletedException(CommandException):
    """Raised to signify that migrations where completed successfully"""
    results : List[Tuple[Migration, Revision]]

class StopMigrationException(CommandException):
    """Raised to signify that we reached the stop point of a migration"""
    migration: str

class ConcurrentMigrationException(CommandException):
    """Raised when another migration is running against the same C* cluster/keyspace"""
    pass 


class Command(object):
    """Base class for all commands"""

    def __init__(self, **keywords):
        self.context = keywords

    def execute(self, project: Project, **keywords):
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
        entities = set(project.entities())
        print(f"[bold blue]Synchronizing the schema for entities: {entities}[/bold blue]")
        for entity in entities:
            print("[bold blue]Syncing: %s [/bold blue]" % entity)
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
    
    def table(self, entity: "Entity", metadata: Metadata) -> "Operation":
        """Generate ops for creating a table"""
        ttl = options(entity, "expire", 0)
        accord = options(entity, "accord", True)    # Accord is enabled by default.
        doc = entity.__doc__ if entity.__doc__ else ""

        columns = []
        properties = fields(entity, CqlProperty)
        for name, prop in properties.items():
            keywords = {
                "name" : name, 
                "type" : prop.ctype,
                "primary": prop.primary,
                "key": prop.key,
                "composite": prop.composite,
                "static": prop.static,
            }
            if prop.index:
                keywords["index"] = prop.index
            if prop.key and not prop.primary:
                order = getattr(prop, "order", None)
                if order:
                    keywords["order"] = order
            field = Field(**keywords)
            columns.append(field)

        op = Table(
            keyspace=entity.keyspace(),
            name=entity.table(),
            columns=columns,
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
                    op = Index(keyspace=keyspace,table=entity.table(),column=prop.name,type=prop.index)
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
            for name in combined:
                if name in properties:
                    prop = properties[name]
                    if name not in schema:
                        op = Column(
                            keyspace=keyspace, 
                            table=entity.table(),
                            name=name, 
                            type=prop.ctype, 
                            static=prop.static
                        )
                        ops.append(op)
                else:
                    op = Drop(
                        target="column",
                        keyspace=keyspace,
                        table=entity.table(),
                        column=name
                    )
                    ops.append(op)
            return ops    
        else:
            raise ValueError(f"Table {entity.table()} does not exist in keyspace")

    def execute(self, project: Project):
        """Generates a new migration that uses your entities as the source of truth"""
        from cqlalchemy.revisions.operations import (Keyspace, Table, Column, Index, Drop)
    
        message = self.context.get("message", "")
        create = self.context.get("create", False)

        revision_id = str(uuid.uuid7())
        filename = project.name(revision_id, message)
        path = project.base() / filename

        operations = []
        if create:
            for entity in project.entities():
                ops = self.process(entity())
                operations.extend(ops)
        output = new_migration.format(
            revision=revision_id,
            message=message,
            operations=operations
        )
        formatted = black.format_str(output, mode=black.Mode(line_length=100))
        with open(path, 'w') as out:
            out.write(formatted)


"""
Migrate:

This command takes a directory of migration files, sorts them topologically, finds & validates their 
accompanying data models from Cassandra, (then can optionally) sequentially run all the migrations 
that have not been applied as of yet (until it reaches the HEAD or a user defined stoppage point using the full revision
id, a part thereof or a tag) - 

This command will retry any failed steps a (configurable) number of times before giving up.


Synopsis:

```bash
$ revision migrate --start <revision | name-tag> --stop <revision | name-tag>
```
"""
class Migrate(Command):
    """Executes and applies any unapplied migration, bringing the database to date"""
    results: List[Tuple["Migration", "Revision"]] 
    applied : Set[str]
    succeeded : bool

    def __init__(self, **keywords):
        self.context = keywords
        self.results = []
        self.applied = set()
        self.succeeded = False

    def apply(self, migration: "Migration", revision: "Revision", deed: "Lock") -> bool:
        """Apply a migration to the database"""
        result = False
        try:
            idempotent = options(migration, "idempotent", False)
            retry = options(migration, "retry", 1)
            duration = options(migration, "duration", minutes(5))

            revision.running = True 
            revision.state = State.STARTED
            revision.save()
            
            migration.execute(revision, deed)
            revision.state = State.APPLIED
            revision.save()

            deed.head = revision 
            deed.migrations.append(revision)
            deed.save()
            
            self.succeeded = True
            result = True
        except TimeoutError:
            print(f"[bold red]Error: Migration {migration.name} exceeded set duration of {duration} seconds[bold red]")
            revision.state = State.FAILED
        except Exception as e:
            print(f"[bold red]Error: Migration {migration.name} failed.[bold red]")
            revision.state = State.FAILED
            if verbose():
                print(f"[bold red]{e}[/bold red]")
            if debug():
                traceback.print_exc()   
        finally:
            revision.completed = datetime.now()
            revision.running = False  
            revision.save()
            return result 
            
    def display(self):
        """Display the status of all the migrations we executed"""
        from rich.table import Table
        terminal = Console()
        terminal.print("")
        if self.succeeded:
            table = Table(title="[bold green underline]Executed Migrations[/bold green underline]")
            table.add_column("Status", justify="left", style="bold blue")
            table.add_column("Name", justify="left", style="bold blue")
            table.add_column("Revision ID", justify="left", style="bold blue")
            table.add_column("Message", justify="left", style="bold blue")
            for migration, revision in self.results:
                table.add_row(
                    str(revision.state.name),
                    str(migration.name),
                    str(migration.revision), 
                    str(migration.message)
                )
            terminal.print(table)

    def filter(self, migrations, start, stop):
        """Filter migrations based on start and stop points"""
        if start and stop:
            start_index = 0
            end_index = 0
            for i, m in enumerate(migrations):
                if start in m.name or start in m.revision:
                    start_index = i
                    break
            for i, m in enumerate(migrations):
                if stop in m.name or stop in m.revision:
                    end_index = i
                    break
            if start_index >= end_index:
                raise MigrationException(f"Stop point {stop} must be greater than start point {start}")

            output = migrations[start_index: end_index+1]
            start_id, end_id = migrations[start_index].name, migrations[end_index].name
            return output
        elif start:
            start_index = 0
            for i, m in enumerate(migrations):
                if start in m.name or start in m.revision:
                    start_index = i
                    break 
            
            output = migrations[start_index:]
            return output
        elif stop:
            start_index = 0
            end_index = len(migrations) - 1 
            for i, m in enumerate(migrations):
                if stop in m.name or stop in m.revision:
                    end_index = i
                    break 
            output = migrations[: end_index+1]
            return output
        else:
            return migrations

    def execute(self, project: Project, allowed_checksums:Iterable[str]=[], rerun:Iterable[str]=[]):
        """Runs migrations from the current state to the HEAD or a user defined stop point"""
        # Check whether another migration is running somewhere else on the infrastructure.
        deed = Lock.instance()
        if deed.running:
            raise ConcurrentMigrationException("Another Migration is running in this C* cluster/keyspace")
        try:
            deed.lock()
            start = self.context.get("start", None)
            stop = self.context.get("stop", None)

            migrations = self.filter(project.migrations(), start, stop)
            for migration in migrations:
                if migration.revision in self.applied:
                    continue
                revision = Revision.find(migration.revision)
                if not revision:
                    print(f"[bold red]Creating a new Revision: {migration.revision}[bold red]")
                    with Atom() as atom:
                        revision = Revision.create(
                            checksum=project.checksum(migration.path),
                            state=State.INITIALIZED,
                            description=migration.message,
                            migration=migration.revision
                        )
                    if self.apply(migration, revision, deed):
                        self.results.append((migration, revision))
                else: 
                    checksum = project.checksum(migration.path)
                    if revision.checksum != checksum: 
                        if checksum in allowed_checksums:
                            revision.checksum = checksum
                            revision.save()
                            if self.apply(migration, revision, deed):
                                self.results.append((migration, revision))
                        else:
                            error = RevisionChecksumException(f"Checksum mismatch in migration: {migration.revision}")
                            error.checksum = checksum
                            raise error 
                    else:
                        if revision.state == State.APPLIED:                      
                            if migration.revision in rerun:
                                if self.apply(migration, revision, deed):
                                    self.results.append((migration, revision))
                            else:
                                error = RevisionAppliedException(f"Revision {migration.revision} has already been applied")
                                error.revision = revision.migration
                                raise error
                        else:                                                      # Or else we simply re-apply the migration. Test this branch too!
                            print("[bold green]Running Migration: %s with status: %s [/bold green]" % (migration.revision, revision.state))
                            if self.apply(migration, revision):
                                self.results.append((migration, revision))
                
                self.applied.add(migration.revision)
                if stop:
                    if stop in migration.revision or stop in migration.name:
                        error = StopMigrationException(f"Migration {migration.revision} reached the stop point")
                        error.migration = migration.revision
                        raise error

            feedback = MigrationCompletedException("Migration Completed Successfully")
            feedback.results = self.results
            raise feedback
        finally:
            deed.release()
            
            
            
"""
Stamp :
This command marks a particular migration as successful, allowing the migration system to skip
it and move to the next migration. 
"""

class Stamp(Command):
    """Marks a particular Migration as successful in C*"""

    def execute(self, env: Project):
        revision = self.context.get("revision", None)
        state = self.context.get("state", State.APPLIED)
        if not revision:
            print("[bold red]Please provide a database revision to search for.[/bold red]")
    
        record = Revision.find(revision)
        if record:
            record.state = state
            record.save()
            print("[bold green]Revision: %s successfully marked as %s[/bold green]" % (revision, state))
        else:
            print("[bold red]No Revision Found For: %s[/bold red]" % revision)


"""
Head:
Finds and prints the most recently applied Revision/Migration to the terminal 
"""
class Head(Command):
    """Prints the most recently applied Revision to the terminal"""

    def execute(self, env: Project):
        from rich.table import Table 

        query = Revision.objects.where(state=State.SUCCEEDED)
        revisions = query.all()
        revisions = sorted(revisions, key=lambda r: r.completed)
        if revisions:
            r = revisions[len[revisions] - 1]
            table = Table(title="Database Revisions")
            terminal = Console()
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
    """Forwards revision to a sp"""

    def execute(self, env: Project):
        entities = env.entities()
        for entity in entities:
            print("Syncing: %s" % entity)
            Schema.create(entity)
        

