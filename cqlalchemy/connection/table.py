
"""Facade for Table supporting implementations for Model, Expando, and Counter"""

import time
import inspect
import functools
import inspect
from threading import RLock
from typing import Dict, Set, Union
from dataclasses import dataclass

import schema

from cqlalchemy.core.builtins import fields, IllegalStateException, now
from cqlalchemy.core.differ import added, commit, changed, changes, OpCode, trackable
from cqlalchemy.connection.cql import Batch, BatchType, AutoCqlQuery
from cqlalchemy.connection.functions import Predicate
from cqlalchemy.core.signals import propagate, Event
from cqlalchemy.core.models import Entity, Counter, Key, Index, CqlProperty, Pointer, BadValueError
from cqlalchemy.options import settings, debug, verbose
from cqlalchemy.connection import offline, ConnectionError
from cqlalchemy.connection.cql import execute


@dataclass
class Metadata(object):
    """A data class for per keyspace schema, and index data"""
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
    def exists(self, entity: Entity):
        """Checks whether @entity exists in our internal metadata"""
        with self.lock:
            entity = self.entities.get(entity.table(), None)
            return bool(entity)

    @classmethod
    def sync(self, entity: Entity):
        """Registers an Entity, creating its keyspace, table, columns, and indexes if necessary"""
        if offline():
            raise ConnectionError("Please connect to C* to continue")
        
        with self.lock:
            kind = entity if inspect.isclass(entity) else entity.__class__
            if not issubclass(kind, Entity) :
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
                    self.update_table(entity)       # Creates any non-existing columns, and indexes
                    self.create_indexes(entity)
                else:
                    self.create_table(entity)
                    self.create_indexes(entity)     # 3. Create any indexes that do not currently exist on C*
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
                if property.indexed():
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
            if debug() and verbose():
                print(query)
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
An object that knows how to persist/read Entity objects to/from C*. 
"""
class Table(object):
    """Implementation proxy for Entity objects"""

    def __init__(self, entity: Entity):
        """Setup the internal state of the Table object"""
        if not issubclass(entity, Entity):
            raise SchemaError("You must provide a subclass of `Entity` to Table objects")
        if issubclass(entity, Counter):
            raise SchemaError("Table does not support `Counter` entities, please use `CounterTable` instead.")
        self.key = Key.create(entity)
        self.properties = fields(entity, CqlProperty)
        self.entity = entity
        self.created = False

    def refresh(self):
        """Synchronizes Schema of the entity with our internal schema"""
        if not self.created and not Schema.exists(self.entity):
            stump = self.entity()
            Schema.sync(stump) # This only creates/syncs the table the first time we see it.
            self.created = True

    def keyspace(self):
        """Returns the configured keyspace of the entity"""
        return self.entity.keyspace()
    
    def insert(self, instance:Entity, unique:bool=False):
        """Insert a new Entity into C*"""
        self.refresh() 
        if instance.saved():
            raise BadValueError("Your Entity has been saved before, please use the `update` function instead")
        if not changed(instance):
            raise BadValueError("There is no modification to save.")
        
        instance.validate()
        query = "INSERT INTO {table} ({columns}) VALUES ({values}){unique}{ttl};"
        unique = " IF NOT EXISTS" if unique else ""
        expire = instance.expire
        ttl = " USING TTL {expire}".format(expire=expire) if expire else ""

        partial = functools.partial(self._screen_, parent=instance)
        operations = [operation for operation in added(instance, screen=partial)]
        columns = [operation.name for operation in operations]
        values = []

        attributes = self.properties
        for operation in operations:  # Ignore the differ for INSERT queries, as we are performing direct conversions.
            property = attributes.get(operation.name)
            if not property.saveable():
                continue  
            value = property.convert(instance, operation.value)
            values.append(value)
        
        if unique:  # Use a LWT, supported by Paxos for this DML query. 
            query = query.format(
                keyspace=instance.keyspace(), 
                table=instance.table(), 
                unique=unique, 
                columns=", ".join(columns), 
                values=", ".join(values), 
                ttl=ttl
            )
        else:
            query = query.format(
                keyspace=instance.keyspace(), 
                table=instance.table(), 
                unique=unique, 
                columns=", ".join(columns), 
                values=", ".join(values), 
                ttl=ttl
            )
        self._persist_(instance, [query,])

    def update(self, instance:Entity):
        """Update an Entity that already exists in C*"""
        self.refresh()
        if not instance.saved():
            raise BadValueError("Your Entity has not been saved before, please use the `insert` function instead")

        instance.validate()
        if changed(instance):
            trackables = dict()
            trackables[instance] = None 

            for attribute in self.properties:
                value = getattr(instance, attribute, None)
                if value and trackable(value):
                    trackables[value] = attribute

            operations = []
            deletion = [OpCode.LDELETE, OpCode.ODELETE, OpCode.MDELETE, OpCode.SDELETE]
            for var in trackables:
                name = trackables[var]
                for operation in changes(var):
                    if name and not operation.name:
                        operation.name = name # Help operations from the children of attributes discover their name. 
                    if operation.code in deletion:
                        query = self._delete_(instance, operation)
                        operations.append(query)
                    else:
                        query = self._update_(instance, operation)
                        operations.append(query)
            self._persist_(instance, operations)
    
    def upsert(self, instance:Entity, predicate:Predicate=None):
        """Update an Entity that already exists in C* directly without reading it"""
        self.refresh()
        if instance.saved():
            raise BadValueError("Expecting an unsaved Entity, please use the `update` function instead")
        if not changed(instance):
            raise BadValueError("There is no modification to save.")
        
        instance.validate()
        query = """UPDATE {table} {ttl} SET\n{data}\nWHERE {key} {predicate} IF EXISTS;"""
        expire = instance.expire
        ttl = " USING TTL {expire}".format(expire=expire) if expire else ""

        predicate = str(predicate) if predicate else ""
        key = self._key_(instance)
        partial = functools.partial(self._screen_, parent=instance)
        operations = [operation for operation in added(instance, screen=partial)]
        assignments = []
        attributes = self.properties
        for operation in operations:  # Ignore the differ for INSERT/UPSERT queries, as we are performing direct conversions.
            property = attributes.get(operation.name)
            if not property.saveable() or (hasattr(property, 'key') and property.key):
                continue  
            value = property.convert(instance, operation.value)
            expr = f"{operation.name} = {value}"
            assignments.append(expr)
        
        data = ", ".join(assignments)
        data = "\t %s" % data
        query = query.format(table=instance.table(), 
            ttl=ttl, data=data, key=key, predicate=predicate
        )
        self._persist_(instance, [query,])
    
    def delete(self, instance: Union[Entity, Pointer]):
        """Delete an entire instance of an Entity from C*"""
        self.refresh()
        if isinstance(instance, Entity) and not instance.saved():
            raise BadValueError("Your Entity has not been saved before")
        try:
            query = "DELETE FROM {table} WHERE {key};"
            query = query.format(table=self.entity.table(), key=self._key_(instance))
            self._remove_(instance, query)
        except Exception as e:
            raise e

    def read(self, key:Pointer):
        """Fetches an Entity from C* and returns it"""
        if not isinstance(key, Pointer):
            raise BadValueError("You can only read from a Table using a `Pointer` object")
        self.refresh()
        instance = AutoCqlQuery(self.entity).where(**key.parts).get()
        return instance

    def truncate(self):
        """Deletes all the rows in this Table"""
        self.refresh()
        try:
            query = "TRUNCATE {table}".format(table=self.entity.table())
            return execute(query, keyspace=self.keyspace())
        except Exception as e:
            raise e
        
    def _persist_(self, instance, operations):
        """Executes queries for this Table, and related objects using a Batch"""
        try: 
            isolated = False
            context = Batch.get()
            if not context:
                context = Batch.create(BatchType.Normal, keyspace=self.keyspace())  
                isolated = True
            for query in operations:
                context.add(query)
            propagate(Event.BEFORE_COMMIT, instance, batch=context) # Allow listeners to join the batch.
            deferred_commit = functools.partial(commit, instance)
            deferred_notify = functools.partial(propagate, Event.AFTER_COMMIT, instance)
            context.after([deferred_commit, deferred_notify])
            if isolated: 
                context.execute()
        except Exception as e:
            raise e
    
    def _remove_(self, pointer, query):
        """Executes queries for this Table, and related objects using a Batch"""
        try: 
            isolated = False
            context = Batch.get()
            if not context:
                context = Batch.create(BatchType.Normal, keyspace=self.keyspace())  
                isolated = True
            context.add(query)
            propagate(Event.BEFORE_REMOVE, pointer, batch=context) # Allow listeners to join the batch.
            deferred_notify = functools.partial(propagate, Event.AFTER_REMOVE, pointer)
            context.after([deferred_notify,])
            if isolated: 
                context.execute()
        except Exception as e:
            raise e

    def _screen_(self, operation, parent):
        """Accept only change operations for this entity"""
        return operation.parent == parent

    def _key_(self, instance: Union[Entity, Pointer]):
        """Internal function used to generate the 'key component' of an update query"""
        pointer = instance.key if isinstance(instance, Entity) else instance
        if pointer is None:
            raise IllegalStateException(f"The `Pointer` for {instance} cannot be None")

        expression = ""
        started = False
        for name, value in pointer.parts.items():
            part = "{name}={value}"
            prop = self.properties.get(name)
            component = part.format(name=name, value=prop.convert(instance, value))
            if started:
                expression = expression + " AND"
            expression = expression + component
            started = True
        return expression
    
    def _update_(self, instance, operation):
        """Generates the appropriate update/assignment expression and query"""
        update_format = """UPDATE {table} {ttl} SET {assignment} WHERE {key}{conditions};"""
        expr = None
        # 1. Deal with direct changes on top level attributes which are descriptors
        if operation.parent == instance:  
            if operation.name in self.properties and operation.code in (OpCode.OCHANGE, OpCode.OSET):
                descriptor = self.properties.get(operation.name)
                value = descriptor.convert(instance, operation.value)
                expr = "{0}={1}".format(operation.name, value)
            else:
                pass # Ignore changes from non-descriptors in the Entity.
        elif operation.parent != instance:
            if operation.name in self.properties and operation.code not in (OpCode.OCHANGE, OpCode.OSET):
                match operation.code:
                    case OpCode.MADD:
                        descriptor = self.properties.get(operation.name)
                        T, V = descriptor.converter
                        key = T.convert(instance, operation.key)
                        value = V.convert(instance, operation.value)
                        expr = "{0}[{1}] = {2}".format(operation.name, key, value)

                    case OpCode.SADD:
                        descriptor = self.properties.get(operation.name)
                        T = descriptor.converter
                        value = T.convert(instance, operation.value)
                        expr = "{name} = {name} + {value}".format(name=operation.name, value=value)
        
                    case OpCode.LAPPEND:
                        descriptor = self.properties.get(operation.name)
                        T = descriptor.converter
                        value = T.convert(instance, operation.value)
                        expr = "{name} = {name} + {value}".format(name=operation.name, value=value)
        
                    case OpCode.LPREPEND:
                        descriptor = self.properties.get(operation.name)
                        T = descriptor.converter
                        value = T.convert(instance, operation.value)
                        expr = "{name} = {value} + {name}".format(name=operation.name, value=value)
        
                    case OpCode.LINSERT:
                        descriptor = self.properties.get(operation.name)
                        T = descriptor.converter
                        value = T.convert(instance, operation.value)
                        expr = "{name}[{index}] = {value}".format(name=operation.name, index=operation.index, value=value)
         
                    case _:
                        raise IllegalStateException("Received an Unsupported OpCode: %s" % operation.code)
        else:
            raise IllegalStateException("Cannot process operations from unknown objects") 

        expression = expr
        table = instance.table()
        expire = operation.ttl if operation.ttl else instance.expire 
        ttl = " USING TTL {expire}".format(expire=expire) if expire else ""
        conditions = " %s" % str(operation.predicate) if operation.predicate else ""
        key = self._key_(instance)
        query = update_format.format(table=table, ttl=ttl, assignment=expression, key=key, conditions=conditions)
        return query 
            
    def _delete_(self, instance, operation):
        """Generates the appropriate DML for removing a member of @instance"""
        delete_format = "DELETE {expression} FROM {table} WHERE {key}{conditions};"
        table = self.entity.table()
        
        expression = None
        match operation.code:
            case OpCode.LDELETE:
                expr = "{name}[{index}]".format(name=operation.name, index=operation.index)
                expression = expr
            case OpCode.ODELETE:
                expr = "{name}".format(name=operation.name)
                expression = expr
            case OpCode.MDELETE:
                descriptor = self.properties.get(operation.name)
                T = descriptor.converter[0]
                key = T.convert(instance, operation.key)
                expr = "{name}[{key}]".format(name=operation.name, key=key)
                expression = expr
            case OpCode.SDELETE:
                expr = "{name} = {name} - {value}".format(name=operation.name, value=operation.value)
                expression = expr
            case _:
                raise IllegalStateException("Received an Unsupported OpCode: %s" % operation.code)
            
        key = self._key_(instance)
        conditions = " %s" % str(operation.predicate) if operation.predicate else ""
        return delete_format.format(expression=expression, table=table, key=key, conditions=conditions)
        
   

