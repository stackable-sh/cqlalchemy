
"""Facade for Table supporting implementations for Model, Expando, and Counter"""


import time
import warnings
from threading import RLock
from typing import Dict

import schema
from bidict import bidict

from cqlalchemy.core.models import Entity, Key, Index
from cqlalchemy.options import settings
from cqlalchemy.connection import world, offline, ConnectionError
from cqlalchemy.connection.cql import execute


class SchemaMismatchError(Exception):
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
    entities : Dict[str, Entity] = bidict()
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
            if not issubclass(entity, Entity):
                raise ValueError("You must provide a `Entity` for us to sync to C*")
            # 1. Create Keyspace on C* and wait for it to reflect.
            keyspace = entity.keyspace().title()
            if keyspace not in self.keyspaces:
                if keyspace in world.cluster.metadata.keyspaces:
                    self.keyspaces[keyspace] = {}
                else:
                    self.create_keyspace(keyspace)
            # 2. Create Table and any new columns on C* and wait for them to reflect
            table = entity.table()
            if table not in self.entities:
                meta = world.cluster.metadata.keyspaces[keyspace]
                if table in meta.tables:
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
            kind = entity.table()
            table = world.cluster.metadata.keyspaces[keyspace][entity.table()]
            indexes = dict()

            for name in entity.__fields__:
                property = entity.__fields__.get(name)
                if property.index:
                    if name not in table.indexes:
                        flag, query = None, None
                        identifier = "INDEX_{0}_{1}".format(entity.table().upper(), name.upper())
                        if isinstance(property.index, bool):
                            flag = Index.ALL
                        else: 
                            flag = property.index
                        # Index the Property on C*
                        match flag:
                            case Index.ALL:
                                if "map" in property.ctype:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {kind}(ENTRIES({name}));"
                                elif "list" in property.ctype or "set" in property.ctype:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {kind}(VALUES({name}));"
                                else:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {kind}({name});"
                            case Index.KEYS:
                                if "map" in property.ctype:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {kind}(KEYS({name}));"
                                else:
                                    raise SchemaMismatchError("You can only index the KEYS of a Map<T,V> ")
                            case Index.VALUES:
                                type = property.ctype
                                if "map" in type or "list" in type or "set" in type:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {kind}(VALUES({name}));"
                                else:
                                    raise SchemaMismatchError("You can only index the KEYS of a Map<T,V>, Set<T>, or List<T>") 
                        execute(query, keyspace=keyspace)
                        indexes[name] = identifier
            
            # Wait for the update to be acknowledged by C*
            while True:
                table = world.cluster.metadata.keyspaces[keyspace][entity.table()]
                results = []
                for name, value in indexes.items():
                    if name not in table.indexes:
                        results.append(False)
                    else:
                        indices = self.indices[entity]
                        property = entity.__fields__.get(name)
                        indices.add(property)
                        results.append(True)

                if all(results):
                    break
                else: 
                    time.sleep(0.3)

    @classmethod
    def update_table(self, entity: Entity):
        """Creates any non-existing columns in C* for @entity, also checks for schema mismatch"""
        if offline():
            raise ConnectionError("Please connect to C* to continue")

        # We ignore columns that exist on C* but are not in the Entity to allow easy migration,
        # users may remove such columns and indexes by invoking Schema.vacuum(entity) at their convenience. 
        with self.lock:
            keyspace = entity.keyspace()
            table = world.cluster.metadata.keyspaces[keyspace][entity.table()]
            for name in entity.__fields__:
                if name in table.columns:
                    column = table.columns[name]
                    property = entity.__fields__.get(name)
                    if column.cql_type != property.ctype:
                        raise SchemaMismatchError("The C* type for Column: {name} does not match your Entity declaration")
                else: # Create the new column.
                    query = """ALTER TABLE {table} ADD {name} {type}"""
                    query.format(table=entity.table(), name=name, type=property.ctype)
                    execute(query, keyspace=keyspace)
                    
            # Wait for the update to be acknowledged by C*
            while True:
                table = world.cluster.metadata.keyspaces[keyspace][entity.table()]
                results = []
                for name in entity.__fields__:
                    if name not in table.columns:
                        results.append(False)
                    else:
                        property = entity.__fields__.get(name)
                        properties = self.keyspaces[keyspace][entity]
                        properties.add(property)
                        results.append(True)
                if all(results):
                    break
                else: 
                    time.sleep(0.3)

    @classmethod 
    def create_table(self, entity: Entity):
        """Creates a Table in C*, will create the Table and new columns"""
        if offline():
            raise ConnectionError("Please connect to C* to continue")
        
        with self.lock:
            query =  """
                CREATE TABLE IF NOT EXISTS {table} (
                    {columns} 
                    PRIMARY KEY ({key})
                ) WITH 
                default_time_to_live = {ttl} AND 
                caching = {'keys' : 'ALL', 'rows_per_partition' : 'ALL'};
            """
            keyspace = entity.keyspace().title()
            table = entity.table().title()
            ttl = entity.expire
           
            columns = []
            for name, property in entity.__fields__.items():
                name, ctype = name.lower(), property.ctype.lower()
                static = "static" if property.static else ""
                part = f"{name} {ctype} {static}"
                columns.append(part.strip())

            key  = Key.create(entity)
            if key.composite:
                start = "(" + ",".join(key.composite) + ")"
                part = f"{start}" + ",".join(key.others)
            else:
                part = ",".join(key.parts)

            columns = ",".join(columns)
            query = query.format(table=table, columns=columns, key=part, ttl=ttl)
            execute(query, keyspace=keyspace)

            # Wait for the Table to be created on C*
            while True:
                meta = world.cluster.metadata.keyspaces[keyspace]
                if table in meta.tables:
                    self.entities[table] = entity
                    self.keyspaces[keyspace][entity] = set(entity.__fields__.values()) 
                    self.indices[entity] = set()
                    break
                time.sleep(0.3)

    @classmethod
    def create_keyspace(self, keyspace):
        """Creates a Keyspace if it does not already exist in C*"""
        if offline():
            raise ConnectionError("Please connect to C* before invoking this method")
        
        with self.lock:
            conf = settings()
            strategy = conf["replication"]
            replication = None
            query = "CREATE KEYSPACE IF NOT EXISTS {keyspace} WITH REPLICATION = {replication} AND DURABLE_WRITES = true;"
            if schema.Schema({"NetworkTopologyStrategy" : int}).validate(strategy):
                value = strategy["NetworkTopologyStrategy"]
                replication = f"{'class' : 'NetworkTopologyStrategy', 'replication_factor' : '{value}'}"
            elif schema.Schema({"NetworkTopologyStrategy" : {str : int}}):
                centres = strategy["NetworkTopologyStrategy"]
                part = ', '.join([f"'{k}'" + ':' + f"'{v}'" for k, v in list(centres.items())]) 
                replication = f"{'class' : 'NetworkTopologyStrategy', {part}}"
            elif schema.Schema({"SimpleStrategy" : int}).validate(strategy):
                value = strategy["SimpleStrategy"]
                replication = f"{'class' : 'SimpleStrategy', 'replication_factor' : '{value}'}"
            query = query.format(keyspace=keyspace, replication=replication)
            execute(query)

            # Wait for the Keyspace to be created on C*
            while True:
                if keyspace in world.cluster.metadata.keyspaces:
                    self.keyspaces[keyspace] = {}
                    break
                time.sleep(0.3)

    @classmethod
    def destroy(self):
        """Deletes all the Keyspace(s) along with all the objects associated with this Schema"""
        if offline():
            raise ConnectionError("Please connect to C* before invoking this method")
        
        warnings.warn("This method will lead to irreversible data loss from the deleted Keyspaces")
        with self.lock:
            for keyspace in self.keyspaces:
                execute(f"DROP KEYSPACE IF EXISTS {keyspace}")

            while True:
                results = []
                for keyspace in self.keyspaces:
                    if keyspace not in world.cluster.metadata.keyspaces:
                        results.append(True)
                    else:
                        results.append(False)

                if all(results):
                    self.keyspaces.clear()
                    self.entities.clear()
                    self.indices.clear()
                    break
                else:
                    time.sleep(0.3)
    
    @classmethod
    def vacuum(self, entity):
        """Deletes any property in C* that doesn't exist in our Entity object"""
        if offline():
            raise ConnectionError("Please connect to C* before invoking this method")
        
        warnings.warn("This method will lead to irreversible data loss from deleted columns")
        with self.lock:
            columns = set()
            for keyspace in self.keyspaces:
                meta = world.cluster.metadata.keyspaces[keyspace]
                table = meta.tables[entity.table()]
                for name in table.columns:
                    if name not in entity.__fields__:
                        execute(f"ALTER TABLE {entity.table()} DROP IF EXISTS {name}", keyspace=entity.keyspace())
                        columns.add(name)
            while True:
                results = []
                meta = world.cluster.metadata.keyspaces[keyspace]
                table = meta.tables[entity.table()]
                for name in columns:
                    if name in table.columns:
                        results.append(False)
                    else:
                        return results.append(True)
                if all(results):
                    break
                else:
                    time.sleep(0.3)

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

