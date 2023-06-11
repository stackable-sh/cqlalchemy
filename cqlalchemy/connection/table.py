
"""Facade for Table supporting implementations for Model, Expando, and Counter"""

import time
import inspect
import warnings
from threading import RLock
from typing import Dict, Set
from dataclasses import dataclass

import schema
from bidict import bidict
from cassandra.metadata import Metadata

from cqlalchemy.core.builtins import fields
from cqlalchemy.core.models import Entity, Key, Index, CqlProperty
from cqlalchemy.options import settings
from cqlalchemy.connection import world, offline, ConnectionError
from cqlalchemy.connection.cql import execute


@dataclass
class Metadata(object):
    keyspaces: Dict[str, Dict[str, Set[str]]]
    indices: Dict[str, Dict[str, Set[str]]]


class SchemaError(Exception):
    """Schema related Errors"""
    pass 

"""
Schema:
Thread Safe Idempotent Schema registry and operations facade. 
"""
class Schema(object):
    """Handles Keyspace and Table operations in C*"""
    lock = RLock()
    keyspaces : Dict[str, Dict[Entity, set]] = {}
    entities : Dict[str, Entity] = {}
    indices : Dict[Entity, set] = {}

    @classmethod
    def get(self, name):
        """Returns the Entity for @name"""
        with self.lock:
            return self.entities.get(name, None)
        
    @classmethod
    def sync(self, entity: Entity):
        """Registers an Entity, creating its keyspace, table, columns, and indexes if necessary"""
        if offline():
            raise ConnectionError("Please connect to C* to continue")
        
        with self.lock:
            if not isinstance(entity, Entity):
                raise ValueError("You must provide a `Entity` for us to sync to C*")
            # 1. Create Keyspace on C* 
            keyspace = entity.keyspace()
            meta = self.metadata(keyspace)
            if keyspace not in self.keyspaces:
                self.create_keyspace(keyspace)
            # 2. Create Table and any new columns on C*
            table = entity.table()
            if table not in self.entities:
                if table in meta.keyspaces[keyspace]:
                    entity if inspect.isclass(entity) else entity.__class__
                    self.entities[table] = entity 
                    self.keyspaces[keyspace][entity] = set()
                    self.indices[entity] = set()
                    self.update_table(entity) # Creates any non-existing
                else:
                    self.create_table(entity)
            # 3. Create any indexes that do not currently exist on C*
            self.create_indexes(entity)
            return entity

    @classmethod
    def create_indexes(self, entity: Entity):
        """Creates any index in @entity that does not exist on C*"""
        if offline():
            raise ConnectionError("Please connect to C* to continue")
        
        with self.lock:
            keyspace = entity.keyspace()
            table = entity.table()
            meta = self.metadata(keyspace)
            indexes = dict()
            attributes = fields(entity, CqlProperty)
            for name, property in attributes.items():
                if property.index:
                    if name not in meta.indices[keyspace][table]:
                        flag, query = None, None
                        identifier = "index_{0}_{1}".format(entity.table(), name.lower())
                        if isinstance(property.index, bool):
                            flag = Index.ALL
                        else: 
                            flag = property.index
                        # Index the Property on C*
                        match flag:
                            case Index.ALL:
                                if "map" in property.ctype:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(ENTRIES({name}));"
                                elif "list" in property.ctype or "set" in property.ctype:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(VALUES({name}));"
                                else:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}({name});"
                            case Index.KEYS:
                                if "map" in property.ctype:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(KEYS({name}));"
                                else:
                                    raise SchemaError("You can only index the KEYS of a Map<T,V> ")
                            case Index.VALUES:
                                type = property.ctype
                                if "map" in type or "list" in type or "set" in type:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(VALUES({name}));"
                                else:
                                    raise SchemaError("You can only index the KEYS of a Map<T,V>, Set<T>, or List<T>") 
                        execute(query, keyspace=keyspace)
                        indexes[name] = identifier
            
            # Wait for the update to be acknowledged by C*
            while True:
                meta = self.metadata(keyspace)
                results = []
                for name, value in indexes.items():
                    indices = meta.indices[keyspace][entity.table()]
                    if value not in indices :
                        results.append(False)
                    else:
                        if entity not in self.indices:
                            self.indices[entity] = set()
                        indices = self.indices[entity]
                        property = attributes.get(name)
                        indices.add(property)
                        results.append(True)
                if all(results):
                    break
                else: 
                    time.sleep(0.1)

    @classmethod
    def update_table(self, entity: Entity):
        """Creates any non-existing columns in C* for @entity, also checks for schema mismatch"""
        if offline():
            raise ConnectionError("Please connect to C* to continue")
        # We ignore columns that exist on C* but are not in the Entity to allow easy migration,
        # users may remove such columns and indexes by invoking Schema.vacuum(entity) at their convenience. 
        with self.lock:
            keyspace = entity.keyspace()
            meta = self.metadata(keyspace)
            for name, property in fields(entity, CqlProperty).items():
                if not property.saveable():
                    continue 
                if name in meta.keyspaces[keyspace][entity.table()]:
                    type = meta.keyspaces[keyspace][entity.table()][name]
                    if type != property.ctype:
                        raise SchemaError("The C* type for Column: {name} does not match your Entity declaration")
                else: # Create the new column.
                    entity = entity if inspect.isclass(entity) else entity.__class__
                    query = "ALTER TABLE IF EXISTS {table} ADD IF NOT EXISTS {name} {type}"
                    query = query.format(table=entity.table(), name=name, type=property.ctype)
                    execute(query, keyspace=keyspace)
                    while True:
                        meta = self.metadata(keyspace)
                        if keyspace in meta.keyspaces:
                            self.keyspaces[keyspace] = {}
                        if entity.table() in meta.keyspaces[keyspace]:
                            self.keyspaces[keyspace] = {entity : set()}
                            self.entities[entity.table()] = entity
                        if name in meta.keyspaces[keyspace][entity.table()]:
                            properties = self.keyspaces[keyspace][entity]
                            properties.add(property)
                            break
                        time.sleep(0.1)

    @classmethod 
    def create_table(self, entity: Entity):
        """Creates a Table in C*, will create the Table and new columns"""
        if offline():
            raise ConnectionError("Please connect to C* to continue")
        with self.lock:
            keyspace = entity.keyspace()
            table = entity.table()
            ttl = entity.expire
            columns = []
            attributes = fields(entity, CqlProperty)
            for name, property in attributes.items():
                if property.saveable():
                    name, ctype = name.lower(), property.ctype.lower()
                    static = "static" if property.static else ""
                    part = f"{name} {ctype} {static}"
                    columns.append(part.strip())

            key  = Key.create(entity)
            if key.composite:
                start = [part for part in key.parts if part in key.composite]
                others = [part for part in key.parts if part not in key.composite]
                start = "(" + ", ".join(start) + ")"
                if not others:
                    part = f"{start}"
                else:
                    part = f"{start}, " + ", ".join(others)
            else:
                part = ", ".join(key.parts)
            columns = ", ".join(columns)
            query =  """
                CREATE TABLE {table} (
                    {columns},
                    PRIMARY KEY ({key})
                ) WITH default_time_to_live = {ttl} 
                AND caching = {{'keys' : 'ALL', 'rows_per_partition' : 'ALL'}};
            """
            query = query.format(table=table, columns=columns, key=part, ttl=ttl)
            execute(query, keyspace=keyspace)
            entity = entity if inspect.isclass(entity) else entity.__class__
            while True:
                meta = self.metadata(keyspace)
                if table in meta.keyspaces[keyspace]:
                    self.entities[table] = entity
                    self.keyspaces[keyspace][entity] = set(attributes.values()) 
                    self.indices[entity] = set()
                    break
                time.sleep(0.1)
            
    @classmethod
    def create_keyspace(self, keyspace):
        """Creates a Keyspace if it does not already exist in C*"""
        if offline():
            raise ConnectionError("Please connect to C* before invoking this method")
        
        with self.lock:
            keyspace = keyspace.lower()
            conf = settings()
            strategy = conf["replication"]
            replication = None
            query = "CREATE KEYSPACE IF NOT EXISTS {keyspace} WITH REPLICATION = {replication} AND DURABLE_WRITES = true;"
            if schema.Schema({"NetworkTopologyStrategy" : int}).validate(strategy):
                value = strategy["NetworkTopologyStrategy"]
                replication = f"{{'class' : 'NetworkTopologyStrategy', 'replication_factor' : '{value}'}}"
            elif schema.Schema({"NetworkTopologyStrategy" : {str : int}}):
                centres = strategy["NetworkTopologyStrategy"]
                part = ', '.join([f"'{k}'" + ':' + f"'{v}'" for k, v in list(centres.items())]) 
                replication = f"{{'class' : 'NetworkTopologyStrategy', {part}}}"
            elif schema.Schema({"SimpleStrategy" : int}).validate(strategy):
                value = strategy["SimpleStrategy"]
                replication = f"{{'class' : 'SimpleStrategy', 'replication_factor' : '{value}'}}"
            query = query.format(keyspace=keyspace, replication=replication)
            execute(query)
            while True:
                meta = self.metadata(keyspace)
                if keyspace in meta.keyspaces:
                    self.keyspaces[keyspace] = {}
                    break
                time.sleep(0.1)
    
    @classmethod
    def metadata(cls, keyspace) -> Metadata:
        """Fetches Keyspace, Table and Index related data from C*"""
        keyspace = keyspace.lower()
        metadata = Metadata(keyspaces={}, indices={})
        # Find Keyspace
        results = execute(f"SELECT * FROM system_schema.keyspaces WHERE keyspace_name='{keyspace}'")
        metadata.keyspaces[keyspace] = {}
        metadata.indices[keyspace] = {}
        
        # Find All Tables In Keyspace
        results = execute(f"SELECT * FROM system_schema.tables WHERE keyspace_name='{keyspace}'")
        if not results:
            return metadata
        else:
            for row in results:
                for name, value in row.items():
                    if name == "table_name":
                        table = value
                        metadata.keyspaces[keyspace][table] = dict()
                        metadata.indices[keyspace][table] = set()
                        # Fetch Columns Per Table
                        cset = execute(f"SELECT * FROM system_schema.columns WHERE keyspace_name='{keyspace}' AND table_name='{table}'")
                        if not cset:
                            return metadata
                        for crow in cset:
                            name, ctype = crow["column_name"], crow["type"]
                            metadata.keyspaces[keyspace][table][name] = ctype
                        # Fetch Indexes Per Table
                        iset = execute(f"SELECT * FROM system_schema.indexes WHERE keyspace_name='{keyspace}' AND table_name='{table}'")
                        if not iset:
                            return metadata
                        for irow in iset:
                            index = irow["index_name"]
                            attributes = metadata.indices[keyspace][table]
                            attributes.add(index)           
            return metadata

    @classmethod
    def clear(self):
        """Clears internal state of Schema without destroying them on C*"""
        with self.lock:
            self.keyspaces.clear()
            self.entities.clear()
            self.indices.clear()

    @classmethod
    def destroy(self):
        """Deletes all the Keyspace(s) along with all the objects associated with this Schema"""
        if offline():
            raise ConnectionError("Please connect to C* before invoking this method")
        with self.lock:
            for keyspace in self.keyspaces:
                execute(f"DROP KEYSPACE IF EXISTS {keyspace}")
            self.clear()
    

"""
Table:

"""
class Table(object):
    """"Abstraction of a C* Table"""

    def truncate(self):
        """Deletes all the rows in this Table"""
        pass 



class ModelTable(Table):
    """Implementation proxy for Model objects"""

    def __init__(self, table):
        super().__init__()





"""
ExpandoTable
Lower level facade for Expando.
"""
class ExpandoTable(Table):
    """Implementation proxy for Expando objects"""
    
    def __init__(self, table):
        super().__init__()



class CounterTable(Table):
    """Implementation proxy for Counter objects"""
    
    def __init__(self, table):
        super().__init__()

