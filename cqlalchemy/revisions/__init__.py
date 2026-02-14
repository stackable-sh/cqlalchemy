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
from typing import List, Union
from enum import Enum

import cqlalchemy
from cqlalchemy.connection.table import Schema
from cqlalchemy.time import minutes
from cqlalchemy.cache import Pair
from cqlalchemy.history import BatchSet, ChangeSet, Audit
from cqlalchemy.revisions.operations import Operation
from cqlalchemy import (
    Entity,
    Model, 
    UUID,
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

    id = UUID(primary=True)
    name = String(required=True, key=True)
    description = String(length=250, index=True)
    checksum = String(required=True)
    running = Boolean(required=True, static=True)
    current = Reference("Revision", required=True, static=True)
    state = Choice(State, required=True, index=True)
    started = DateTime(now=True, index=True)
    completed = DateTime(index=True)

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

    def __init_subclass__(cls, idempotent=False, retry=0, duration=minutes(1)):
        cls.__options__ = {}
        cls.__options__["idempotent"] = idempotent
        cls.__options__["retry"] = retry
        cls.__options__["duration"] = duration

    def __init__(self, revision: str):
        if not revision:
            raise ValueError("Please provide a valid and `unique` revision number")
        self.revision = revision

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

    def before(self):
        """Perform any data migrations required before the schema change"""
        pass 

    def actions(self) -> List[Operation]:
        """Sequential actions that perform the actual schema migration"""
        return []

    def after(self):
        """Perform any data migrations, post schema change"""
        pass 
    


class Project(object):
    """Encapsulates the environment in which migrations are run"""
    initialized: bool 

    def __init__(self, root: Union[str, Path]):
        self.root = root
        self.required = ["__init__.py", "project.py", "versions", "README", os.path.join("versions", "__init__.py")]
        self.dirs = {"versions",}
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
    
    def setup(self):
        """Setup the environment including configuring C* access"""
        try:
            if not self.initialized:
                sys.path.extend(self.classpath())
                # Register the schema with C*
                if not Schema.get(Revision.table()):
                    Schema.put(Revision)
                if not Schema.exists(Revision):
                    new = Revision()
                    Schema.create(new)
                self.initialized = True 
        except Exception as e:
            raise e
    
    def connect(self):
        """Configure C* access"""
        pass 
        
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

    def load(self, file:Path) -> Migration:
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
    
    def migrations(self) -> List[Migration]:
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
    
    def _find_(self) -> List[Entity]:
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
        system = []  #CQLAlchemy Built Models 
        system.extend(self._find_())
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


def load(dir: str) -> Project:
    """Allows you to load an existing Environment from a revision that is already on disk"""
    path = Path(os.path.join(dir, "project.py"))
    if not os.path.exists(path):
        raise MigrationException(f"No project file found at: {path}")
    print(f"Loading Path: {path}")
    function = lambda entity : isinstance(entity, Project)
    project = require(Path(path), matcher=function)
    if project:
        return project 
    else:
        raise MigrationException("No environment context was found at: %s" % dir)


def require(path: Path, matcher):
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
        raise MigrationException(f"Error loading module: {path}")