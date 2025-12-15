"""
Migrations
==========
CqlAlchemy supports only forward migrations, this means that all changes to the data store must be 
made in a new/fresh migration (including reversing a migration). 


"""

import os
import sys
from datetime import datetime
from datetime import datetime
import importlib
from pathlib import Path
from typing import List
from enum import Enum

from rich import print

import cqlalchemy
from cqlalchemy.time import minutes
from cqlalchemy.cache import Pair
from cqlalchemy.history import BatchSet, ChangeSet, Audit
from cqlalchemy.migrate.operations import Operation
from cqlalchemy import (
    Entity,
    Model, 
    String,
    Choice, 
    DateTime, 
    Boolean,
    Reference,
    Set,
)

class MigrationException(Exception):
    pass 

class StopMigration(MigrationException):
    pass 

class FailedMigrationException(MigrationException):
    pass 


State = Enum(
    "State", 
    [
        "INITIALIZED",
        "SUCCEEDED", 
        "FAILED", 
        "RUNNING", 
        "SKIPPED"
    ]
)

class Revision(Model, version=False, batch=False):
    """C* Record of a Database Revision"""

    id = String(primary=True)
    path = String(required=True)
    description = String(length=100, index=True)
    checksum = String(required=True)
    running = Boolean(required=True, static=True)
    current = Reference("Revision", required=True, static=True)
    labels = Set(String, index=True)
    state = Choice(State, required=True, index=True)
    started = DateTime(now=True, index=True)
    completed = DateTime(index=True)


"""
Migration

An (optionally idempotent) abstraction that performs the actual data, and schema migration.
Your generated (or hand written migrations) will inherit from this base class. 

Since C* does not have transactions (as of 4.1), migrations in C* should be written idempotently, 
so that they can be retried multiple times safely until they complete sucessfully. If your migration is 
marked as `idempotent` CqlAlchemy will retry each failed step in your migration `retry` (configurable) of 
times to see if it succeeds before it gives up.

"""

class Migration(object):
    """Python migrations must implement this interface"""

    def __init_subclass__(cls, idempotent=False, retry=0, duration=minutes(1)):
        cls.__options__ = {}
        cls.__options__["idempotent"] = idempotent
        cls.__options__["retry"] = retry
        cls.__options__["duration"] = duration

    def __init__(self, revision: str, labels : List[str]=[]):
        if not revision:
            raise ValueError("Please provide a valid and `unique` revision number")
        self.revision = revision
        self.labels = labels

    @property
    def checksum(self):
        """Returns the checksum of this migration revision"""
        pass 
    
    @property
    def path(self):
        """Returns the filename for this Migration"""
        pass 

    def get(self, create=False) -> Revision:
        """Returns the Revision entity model stored in C* for this object"""
        record = Revision.read(self.revision)
        if record is not None:
            return record 
        else:
            if create:
                record = Revision.create(
                    id=self.revision, 
                    checksum=self.checksum,
                    path=self.path,
                    running=False,
                    state=State.INITIALIZED,
                    started=datetime.now()
                )
            return record

    def prepare(self):
        """Perform preparatory work (that does not involve actual migration)"""
        pass 

    def before(self):
        """Perform any data migrations required before the schema change"""
        pass 

    def actions(self) -> List[Operation]:
        """Sequential actions that perform the actual schema migration"""
        return []

    def after(self):
        """Perform any data migrations, post schema change"""
        pass 
    
    def shutdown(self):
        """Perform any clean up actions here"""
        pass 


class EnvironmentContext(object):

    def __init__(self, root):
        self.root = root
        self.required = ["__init__.py", "env.py", "README", "versions", os.path.join("versions", "__init__.py")]
        self.dirs = {"versions",}
        self.configure()

    def configure(self):
        """Setup the environment including configuring C* access"""
        try:
            if not self.initialized:
                sys.path.extend(self.classpath)
            cqlalchemy.configure(
                keyspace="Test", 
                servers=["localhost",],
                debug=True, 
                verbose=True,
            )
            self.initialized = True 
        except Exception as e:
            raise e

    def shutdown(self):
        """Release any system wide resources at the end of all migrations"""
        cqlalchemy.shutdown()
        self.initialized = False 
    
    def name(self, revision: str, description: str) -> str:
        """Create a unique `name` for a migration from @description"""
        if not len(revision >= 12):
            raise MigrationException("Please provide a revision GUID longer than 12 characters")
        if not description.isalnum():
            raise MigrationException("Please provide only alpha numerics in your description")
        
        revision = revision[:12]
        size = len(description) if len(description) <= 40 else 40
        slug = description[:size].replace(" ", "_")
        return  f"{revision}_{slug}.py"
    
    def exists(self):
        try:
            path = self.base()
            if path:
                return True
        except MigrationException:
            return False

    def load(self, file) -> Migration:
        """Loads a migration from @file and return it"""
        try:
            if not self.initialized:
                raise MigrationException("Please initialize this environment before attempting to load Migration(s)")
            
            file = os.path.join(self.base(), file)
            if not os.path.exists(file):
                raise MigrationException("We couldn't find file: %s on disk" % file)

            path = Path(file)
            function = lambda entity : isinstance(entity, Migration)
            migration = require(path, function)
            if not migration:
                raise MigrationException("We could not find any Migration in: %s" % file)
            return migration 
        except Exception as e:
            raise e
 
    def classpath(self) -> List[str]:
        """Return paths to modules that you want to be importable in a migration"""
        return [".",]
    
    def search(self) -> List[str]:
        """Returns paths that you want to search for Entities within your project"""
        return []
    
    def migrations(self):
        """Returns all the migrations within this context in a lexically sort order"""
        if not self.initialized:
            raise MigrationException("Please initialize this environment before attempting to load Migration(s)")
    
        names, executables = [], {}
        function = lambda entity : isinstance(entity, Migration)
        modules = os.path.join(self.base(), "versions")
        for name in os.listdir(modules):
            if name.endswith(".py") and not name.startswith("__"):
                path = Path(name)
                found = require(path, function)
                if found:
                    names.append(name)
                    executables[name] = found 
        names = sorted(names) # Sort the migrations topologically and return them
        results = [executables[name] for name in names]
        return results
    
    def _search_for_entities_(self) -> List[Entity]:
        """Finds and returns all the entities from the classpaths"""
        results = []
        function = lambda entity : issubclass(entity, Entity)
        for directory in self.search():
            for path in Path(directory).glob('*.py'):
                found = require(path, function)
                if found:
                    results.append(found)
        return results

    def entities(self) -> List[Entity]:
        """Returns models that ship with cqlalchemy by default, extend to add your own entities"""
        system = [Pair, Audit, ChangeSet, BatchSet, Revision,]  #CQLAlchemy Built Models 
        system.extend(self._search_for_entities_())
        return system

    def base(self) -> Path:
        """Returns the location where migration scripts are stored"""
        root =  os.path.join(os.getcwd(), self.root)
        if not os.path.exists(root):
            raise MigrationException("Migration directory does not exist.")
        for name in self.required:
            path = os.path.join(root, name)
            if not os.path.exists(path):
                raise MigrationException("Incomplete Migration Environment: %s was not found in the root directory" % name)
        return Path(root)


def load(directory: str) -> EnvironmentContext:
    """Allows you to load an existing Environment from a revision that is already on disk"""
    path = Path(os.path.join(directory, "env.py"))
    function = lambda entity : isinstance(entity, EnvironmentContext)
    env = require(path, matcher=function)
    if env:
        env.configure()
        return env 
    else:
        raise MigrationException("No environment context was found at: %s" % directory)


def require(path: Path, matcher):
    """An importer routine that allows you find & return anything that @matcher matches in @path"""
    module = path.stem
    spec = importlib.util.spec_from_file_location(module, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  
    for member in dir(module):
        entity = getattr(module, member)
        if entity and matcher(entity):
            return entity
        else:
            return None


