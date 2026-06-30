# Copyright 2026 Iroiso Ikpokonte
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Migrations
==========
CqlAlchemy supports only forward migrations, this means that all changes to the data store must be
made in a new/fresh migration (including reversing a migration).


"""

import os
import sys
import hashlib
from datetime import datetime
import importlib
from pathlib import Path
from typing import List, Union, Self, Callable
from enum import Enum

from rich import print


import cqlalchemy
from cqlalchemy.connection.cql import Level
from cqlalchemy.exceptions import BaseException
from cqlalchemy.connection.table import Schema
from cqlalchemy.time import minutes
from cqlalchemy.revisions.operations import Operation
from cqlalchemy.connection.cql.fluent import update
from cqlalchemy import List as Vector
from cqlalchemy import (
    Entity,
    Model,
    UUID,
    String,
    Integer,
    Choice,
    DateTime,
    Boolean,
    Reference,
)


class MigrationException(BaseException):
    pass


State = Enum(
    "State",
    [
        "INITIALIZED",
        "STARTED",
        "BEFORE_SCHEMA_CHANGE",
        "SCHEMA_CHANGE",
        "AFTER_SCHEMA_CHANGE",
        "APPLIED",
        "FAILED",
        "SKIPPED",
    ],
)


class Revision(Model, version=False):
    """C* Record of a Database Revision"""

    id = UUID(primary=True)
    migration = String(required=True, key=True)
    checksum = String(required=True, index=True)
    description = String(length=250, index=True)
    state = Choice(State, required=True, index=True)
    created = DateTime(now=True, index=True)
    started = DateTime(index=True)
    completed = DateTime(index=True)

    @classmethod
    def find(cls, migration: str):
        """Find a revision by its migration name"""
        return Revision.objects.where(migration=migration).filter().get()


class Lock(Model, version=False):
    """Runtime record of schema migrations"""

    id = Integer(primary=True)
    created = DateTime(key=True)
    head = Reference(Revision, static=True)
    running = Boolean(required=True, static=True)
    migrations = Vector(Revision)
    modified = DateTime(index=True)

    @classmethod
    def lock(cls):
        """Acquire lock"""
        instance = Lock.instance()
        if instance.running:
            raise MigrationException(
                "Another migration is already running, please try again later"
            )
        update(Lock).set(running=True, modified=datetime.now()).where(
            id=1, created=instance.created
        ).execute()

    @classmethod
    def release(cls):
        """Release lock"""
        instance = Lock.instance()
        if not instance.running:
            raise MigrationException(
                "There is no currently running migration to release"
            )
        update(Lock).set(running=False, modified=datetime.now()).where(
            id=1, created=instance.created
        ).execute()

    @classmethod
    def instance(cls):
        """Returns the singleton instance of this migration"""
        found = Lock.objects.where(id=1).get()
        if not found:
            found = Lock(
                id=1,
                created=datetime.now(),
                running=False,
                migrations=[],
                modified=datetime.now(),
            )
            found.save()
        return found


"""
Migration

An (optionally idempotent) abstraction that performs the actual data, and schema migration.
Your generated (or hand written migrations) will inherit from this base class. 

Migrations in C* should be written idempotently, so that they can be retried multiple times safely 
until they complete sucessfully. If your migration is marked as `idempotent` CqlAlchemy will retry each 
failed step in your migration `retry` (configurable) of times to see if it succeeds before it gives up.

"""


class Migration(object):
    """Python migrations must implement this interface"""

    revision: str = None
    message: str = None
    path: Path = None

    def __init_subclass__(cls, idempotent=False, retry=0, duration=minutes(1)):
        cls.__options__ = {}
        cls.__options__["idempotent"] = idempotent
        cls.__options__["retry"] = retry
        cls.__options__["duration"] = duration

    def __init__(self, revision: str, message: str, path: Path):
        if not revision:
            raise ValueError("Please provide a valid and `unique` revision GUID")
        self.revision = revision
        self.message = message
        self.path = path

    @property
    def name(self) -> str:
        """Returns the name of this Migration"""
        return self.path.name

    def consistency(self):
        """Default consistency level for the migration. Returns `Level.Quorum` by default"""
        return Level.Quorum

    def execute(self, revision: Revision, deed: Lock):
        """Execute for a maximum of `duration` seconds, retrying if `retry` is True"""
        try:
            with self.consistency():
                revision.state = State.BEFORE_SCHEMA_CHANGE
                revision.started = datetime.now()
                revision.save()

                self.before()

                revision.state = State.SCHEMA_CHANGE
                revision.save()

                for operation in self.actions():
                    operation.execute()
                    operation.validate()

                revision.state = State.AFTER_SCHEMA_CHANGE
                revision.save()

                self.after()
                revision.state = State.APPLIED
                revision.completed = datetime.now()
                revision.save()

                deed.head = revision
                deed.migrations.append(revision)
                deed.save()

        except Exception as e:
            with self.consistency():
                revision.state = State.FAILED
                revision.completed = datetime.now()
                revision.save()
            raise e

    def before(self):
        """Perform any data migrations required before the schema change"""
        pass

    def actions(self) -> Union[Operation, List[Operation]]:
        """Sequential actions that perform the actual schema migration"""
        return []

    def after(self):
        """Perform any data migrations, post schema change"""
        pass


"""
Project

An abstraction that encapsulates the environment in which migrations are run.

"""


class Project(object):
    """Encapsulates the environment in which migrations are run"""

    initialized: bool = False
    revision_name_template: str = "rev_{revision}_{slug}.py"

    def __init__(self, root: Union[str, Path]):
        self.root = root
        self.required = [
            "__init__.py",
            "project.py",
            "versions",
            "README",
            os.path.join("versions", "__init__.py"),
        ]
        self.dirs = {
            "versions",
        }
        self.initialized = False

    def valid(self):
        """Check if this project is valid"""
        required = set(self.required)
        required.remove("README")
        for file in self.required:
            if not os.path.exists(os.path.join(self.root, file)):
                print(f"Missing Required File: {file}")
                return False
        return True

    def setup(self, force=False):
        """Setup the environment including configuring C* access"""
        try:
            if force or not self.initialized:
                sys.path.extend(self.classpath())
                # Register the schema with C*
                required = [
                    Revision,
                    Lock,
                ]
                for cls in required:
                    if not Schema.get(cls.table()):
                        Schema.put(cls)
                    if not Schema.exists(cls):
                        new = cls()
                        Schema.create(new)
                self.initialized = True
        except Exception as e:
            raise e

    def connect(self):
        """Configure C* access"""
        raise NotImplementedError(
            "Please implement this method in your Project subclass"
        )

    def checksum(self, path: Union[str, Path]) -> str:
        """Returns the checksum of a file within this Project"""
        path = Path(os.path.abspath(path))
        if os.path.exists(path):
            return hashlib.md5(open(path, "rb").read()).hexdigest()
        else:
            raise MigrationException(f"File: {path} does not exist on the file system")

    def shutdown(self):
        """Release any system wide resources at the end of all migrations"""
        cqlalchemy.shutdown()
        self.initialized = False

    def name(self, revision: str, description: str) -> str:
        """Create a unique `name` for a migration from @description"""
        size = len(description) if len(description) <= 40 else 40
        description = description[:size].replace(" ", "_")
        description = [c for c in description if c.isalnum() or c == "_"]
        description = "".join(description)

        revision = [c for c in revision if c.isalnum() or c == "_"]
        revision = "".join(revision)
        if len(revision) >= 12:
            revision = revision[:8]
        if not description:
            raise MigrationException(
                "Please provide only alpha numerics in your description"
            )
        return self.revision_name_template.format(revision=revision, slug=description)

    def exists(self):
        return os.path.exists(self.root)

    def get(self, file: Path) -> Migration:
        """Loads a migration from @file and return it"""
        try:
            if not self.initialized:
                raise MigrationException(
                    "Please initialize this environment before attempting to load Migration(s)"
                )

            file = os.path.join(self.base(), file)
            if not os.path.exists(file):
                raise MigrationException("We couldn't find file: %s on disk" % file)

            path = Path(file)
            function = lambda entity: isinstance(entity, Migration)
            migration = self.require(path, function)
            if not migration:
                raise MigrationException(
                    "We could not find any Migration in: %s" % file
                )
            return migration
        except Exception as e:
            raise e

    def classpath(self) -> List[str]:
        """Return paths to modules that you want to be importable in a migration"""
        return [
            ".",
        ]

    def search(self) -> List[str]:
        """Returns paths that you want to search for Entities within your project"""
        return []

    def last(self) -> Revision:
        """Returns the last applied migration"""
        revisions = Revision.objects.all()
        if not revisions:
            return None
        revisions = [r for r in revisions if r.state == State.APPLIED]
        if not revisions:
            return None
        return max(revisions, key=lambda x: x.started)

    def migrations(self, ignore: List[Union[str, Path]] = []) -> List[Migration]:
        """Returns all the migrations within this context in a lexically sorted order"""
        if not self.initialized:
            raise MigrationException(
                "Please initialize this environment before attempting to load Migration(s)"
            )

        names, executables = [], {}
        function = lambda entity: isinstance(entity, Migration)
        modules = self.base()
        for name in os.listdir(modules):
            if name.endswith(".py") and not name.startswith("__"):
                path = Path(os.path.join(modules, name))
                if path in ignore:
                    continue
                found = self.require(path, function)
                if found:
                    names.append(found.revision)
                    executables[found.revision] = found
        lexical = list(
            sorted(names)
        )  # Sort the migrations topologically and return them
        results = [executables[name] for name in lexical]
        return results

    def _find_(self) -> List[Entity]:
        """Finds and returns all the entities from the classpaths"""
        results = []
        function = lambda entity: issubclass(entity, Entity)
        for directory in self.search():
            for path in Path(directory).glob("*.py"):
                found = self.require(path, function)
                if found:
                    results.append(found)
        return results

    def entities(self) -> List[Entity]:
        """Returns models that ship with cqlalchemy by default, extend to add your own entities"""
        system = []
        system.extend(self._find_())
        return system

    def base(self) -> Path:
        """Returns the location where migration scripts are stored"""
        path = Path(os.path.abspath(self.root)) / "versions"
        if not os.path.exists(path):
            raise MigrationException("Migration directory does not exist.")
        return path

    @classmethod
    def boot(cls, dir: str) -> Self:
        """Allows you to load an existing Environment from a revision that is already on disk"""
        path = Path(os.path.join(dir, "project.py"))
        if not os.path.exists(path):
            raise MigrationException(f"No project file found at: {path}")
        function = lambda entity: isinstance(entity, Project)
        project = cls.require(Path(path), matcher=function)
        if project:
            return project
        else:
            raise MigrationException("No environment context was found at: %s" % dir)

    @classmethod
    def require(cls, path: Path, matcher: Callable):
        """An importer routine that allows you find & return anything that @matcher matches in @path"""
        try:
            module = path.stem
            spec = importlib.util.spec_from_file_location(module, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for member in dir(module):
                entity = getattr(module, member)
                if entity and matcher(entity):
                    return entity
            return None
        except Exception as e:
            raise e
