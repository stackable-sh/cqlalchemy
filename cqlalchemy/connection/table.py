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

"""Facade for writing to C* with supporting implementations for Model, Expando, and Counter"""

from cqlalchemy.core.differ import Operation
import time
import inspect
from functools import partial
import inspect
from threading import RLock
from typing import Dict, Set, Union, Iterable
from dataclasses import dataclass

import schema
from rich import print

from cqlalchemy.core.differ import added, commit, changed, changes, Action, trackable
from cqlalchemy.connection.cql import Batch, BatchType, SelectQuery, Atom, Group
from cqlalchemy.connection.functions import Predicate
from cqlalchemy.core.signals import propagate, subscribe, Event
from cqlalchemy.core.models import (
    options,
    Entity,
    Key,
    Index,
    CqlProperty,
    Pointer,
)
from cqlalchemy.options import settings, debug
from cqlalchemy.connection import offline
from cqlalchemy.connection.cql import execute
from cqlalchemy.core.builtins import fields
from cqlalchemy.exceptions import (
    BadValueError,
    CqlQueryException,
    IllegalStateException,
    ConnectionError,
    IsolatedStaticFieldException
)


@dataclass
class Metadata(object):
    """A data class for per keyspace schema, and index data"""

    keyspaces: Dict[str, Dict[str, Set[str]]]
    indexes: Dict[str, Dict[str, Set[str]]]

    @classmethod
    def fetch(cls, keyspace):
        """Fetches metadata information from C* and returns it"""
        keyspace = keyspace.lower()
        metadata = cls(keyspaces={}, indexes={})

        # Find Keyspace
        results = execute(
            f"SELECT * FROM system_schema.keyspaces WHERE keyspace_name='{keyspace}'"
        )
        if results:
            metadata.keyspaces[keyspace] = {}
            metadata.indexes[keyspace] = {}
            
        # Find All Tables In Keyspace
        results = execute(
            f"SELECT * FROM system_schema.tables WHERE keyspace_name='{keyspace}'"
        )
        if not results:
            return metadata
        else:
            for row in results:
                for name, value in row.items():
                    if name == "table_name":
                        table = value
                        metadata.keyspaces[keyspace][table] = dict()
                        metadata.indexes[keyspace][table] = set()
                        # Fetch Columns Per Table
                        cset = execute(
                            f"SELECT * FROM system_schema.columns WHERE keyspace_name='{keyspace}' AND table_name='{table}'"
                        )
                        if not cset:
                            return metadata
                        for crow in cset:
                            name, ctype = crow["column_name"], crow["type"]
                            metadata.keyspaces[keyspace][table][name] = ctype
                        # Fetch Indexes Per Table
                        iset = execute(
                            f"SELECT * FROM system_schema.indexes WHERE keyspace_name='{keyspace}' AND table_name='{table}'"
                        )
                        if not iset:
                            return metadata
                        for irow in iset:
                            index = irow["index_name"]
                            attributes = metadata.indexes[keyspace][table]
                            attributes.add(index)
            return metadata


class SchemaError(Exception):
    """Schema related Errors"""
    pass


"""
Schema:
Thread Safe, Idempotent Schema & Entity registry and Operations Facade. 
"""


class Schema(object):
    """Handles Keyspace and Table Schema operations in C*"""

    lock = RLock()
    keyspaces: Dict[str, Dict[Entity, set]] = {}
    entities: Set[Entity] = set()
    indexes: Dict[Entity, set] = {}
    registry: Dict[str, Entity] = {}

    @classmethod
    def refresh(cls, entity: Entity):
        """Synchronizes Schema of the entity with our internal schema"""
        if not cls.exists(entity):
            cls.put(entity)
            cls.create(entity)
            
    @classmethod
    def get(self, name):
        """Returns the Entity for @name"""
        with self.lock:
            name = name.lower()
            return self.registry.get(name, None)

    @classmethod
    def put(self, entity: Entity):
        if not issubclass(entity, Entity):
            raise ValueError("Please provide an Entity class")
        with self.lock:
            self.registry[entity.table()] = entity

    @classmethod
    def exists(self, entity: Entity):
        """Checks whether @entity has been created and exists in our internal schema dict"""
        with self.lock:
            return entity in self.entities

    @classmethod
    def create(self, entity: Entity):
        """Registers Entity, creating|syncing its keyspace, table, columns, and indexes if necessary"""
        try:
            if offline():
                raise ConnectionError("Please connect to C* to continue")

            with self.lock:
                kind = entity if inspect.isclass(entity) else entity.__class__
                if not issubclass(kind, Entity):
                    raise ValueError("You must provide a `Entity` for us to sync to C*")
                try:
                    sentinel = kind()
                except Exception as e:
                    raise SchemaError("Every `Entity` must support an empty constructor")

                # 1. Create Keyspace on C*
                keyspace = entity.keyspace()
                meta = self.metadata(keyspace)
                if keyspace not in self.keyspaces:
                    self.create_keyspace(keyspace)
                # 2. Create Table and any new columns on C*
                table = entity.table()
                if entity not in self.entities:
                    entity = entity if inspect.isclass(entity) else entity.__class__
                    if table in meta.keyspaces.get(keyspace, {}):
                        # Creates any non-existing columns, and indexes
                        self.entities.add(entity)
                        self.keyspaces[keyspace][entity] = set()
                        self.indexes[entity] = set()
                        self.update_table(entity)
                        self.create_indexes(entity)
                    else:
                        # 3. Create any indexes that do not currently exist on C*
                        self.create_table(entity)
                        self.create_indexes(entity)
                return entity
        except Exception as e:
            raise e

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
                    if name not in meta.indexes[keyspace][table]:
                        flag, query = None, None
                        identifier = "index_{0}_{1}".format(
                            entity.table(), name.lower()
                        )
                        if isinstance(property.index, bool):
                            flag = Index.All
                        else:
                            flag = property.index
                        # Index the Property on C*
                        match flag:
                            case Index.All:
                                if "map" in property.ctype:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(ENTRIES({name}));"
                                elif (
                                    "list" in property.ctype or "set" in property.ctype
                                ):
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(VALUES({name}));"
                                else:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}({name});"
                            case Index.Keys:
                                if "map" in property.ctype:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(KEYS({name}));"
                                else:
                                    raise SchemaError(
                                        "You can only index the KEYS of a Map<T,V> "
                                    )
                            case Index.Values:
                                type = property.ctype
                                if "map" in type or "list" in type or "set" in type:
                                    query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(VALUES({name}));"
                                else:
                                    raise SchemaError(
                                        "You can only index the KEYS of a Map<T,V>, Set<T>, or List<T>"
                                    )
                        execute(query, keyspace=keyspace)
                        indexes[name] = identifier

            # Wait for the update to be acknowledged by C*
            while True:
                meta = self.metadata(keyspace)
                results = []
                for name, value in indexes.items():
                    indexes = meta.indexes[keyspace][entity.table()]
                    if value not in indexes:
                        results.append(False)
                    else:
                        if entity not in self.indexes:
                            self.indexes[entity] = set()
                        indexes = self.indexes[entity]
                        property = attributes.get(name)
                        indexes.add(property)
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
                        raise SchemaError(
                            "The C* type for Column: {name} does not match your Entity declaration"
                        )
                else:  # Create the new column.
                    entity = entity if inspect.isclass(entity) else entity.__class__
                    query = (
                        "ALTER TABLE IF EXISTS {table} ADD IF NOT EXISTS {name} {type}"
                    )
                    query = query.format(
                        table=entity.table(), name=name, type=property.ctype
                    )
                    execute(query, keyspace=keyspace)
                    while True:
                        meta = self.metadata(keyspace)
                        if keyspace in meta.keyspaces:
                            self.keyspaces[keyspace] = {}
                        if entity.table() in meta.keyspaces[keyspace]:
                            self.keyspaces[keyspace] = {entity: set()}
                            self.entities.add(entity)
                        if name in meta.keyspaces[keyspace][entity.table()]:
                            properties = self.keyspaces[keyspace][entity]
                            properties.add(property)
                            break
                        time.sleep(0.1)

    @classmethod
    def create_table(self, entity: Entity):
        """Creates a Table in C*, will create the Table and new columns"""
        from cqlalchemy.core.models import CounterEntity

        if offline():
            raise ConnectionError("Please connect to C* to continue")
        with self.lock:
            keyspace = entity.keyspace()
            table = entity.table()
            ttl = options(entity, "expire", 0)
            accord = options(entity, "accord", True)    # Accord is enabled by default.
            doc = entity.__doc__ if entity.__doc__ else ""
            columns = []
            attributes = fields(entity, CqlProperty)
            for name, property in attributes.items():
                if property.saveable():
                    name, ctype = name.lower(), property.ctype.lower()
                    static = "static" if property.static else ""
                    part = f"{name} {ctype} {static}"
                    columns.append(part.strip())

            key = Key.create(entity)
            # If there is an composite key, generate the approriate CQL part
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

            clustering = ""
            if key.cluster:  # If there are clustering keys, create clustering order.
                results = []
                for name in key.cluster:
                    attribute = attributes.get(name)
                    if attribute.order:
                        order = "{name} {order}".format(
                            name=name, order=attribute.order
                        )
                        results.append(order)
                if results:
                    cluster = ", ".join(results)
                    clustering = f" AND CLUSTERING ORDER BY ({cluster})"
            klass = entity if isinstance(entity, type) else entity.__class__
            mode = "off" if issubclass(klass, CounterEntity) or not accord else "full"
            columns = ", ".join(columns)
            query = """
            CREATE TABLE {table} (
                {columns},
                PRIMARY KEY ({key})
            ) 
            WITH default_time_to_live = {ttl}{clustering}
            AND transactional_mode = '{mode}'
            AND caching = {{'keys' : 'ALL', 'rows_per_partition' : 'ALL'}}
            AND comment = '{comment}';
            """
            query = query.format(
                table=table,
                columns=columns,
                key=part,
                clustering=clustering,
                ttl=ttl,
                mode=mode,
                comment=doc,
            )
            execute(query, keyspace=keyspace)
            entity = entity if inspect.isclass(entity) else entity.__class__
            while True:
                meta = self.metadata(keyspace)
                if table in meta.keyspaces[keyspace]:
                    self.entities.add(entity)
                    self.keyspaces[keyspace][entity] = set(attributes.values())
                    self.indexes[entity] = set()
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
            if schema.Schema({"NetworkTopologyStrategy": int}).validate(strategy):
                value = strategy["NetworkTopologyStrategy"]
                replication = f"{{'class' : 'NetworkTopologyStrategy', 'replication_factor' : '{value}'}}"
            elif schema.Schema({"NetworkTopologyStrategy": {str: int}}):
                centres = strategy["NetworkTopologyStrategy"]
                part = ", ".join(
                    [f"'{k}'" + ":" + f"'{v}'" for k, v in list(centres.items())]
                )
                replication = f"{{'class' : 'NetworkTopologyStrategy', {part}}}"
            elif schema.Schema({"SimpleStrategy": int}).validate(strategy):
                value = strategy["SimpleStrategy"]
                replication = (
                    f"{{'class' : 'SimpleStrategy', 'replication_factor' : '{value}'}}"
                )
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
        return Metadata.fetch(keyspace)

    @classmethod
    def clear(self):
        """Clears internal state of Schema without destroying them on C*"""
        with self.lock:
            self.keyspaces.clear()
            self.entities.clear()
            self.indexes.clear()
            self.registry.clear()

    @classmethod
    def destroy(self, keyspace=None, tables=[]):
        """Deletes all the Keyspace(s) along with all the objects associated with this Schema"""
        if offline():
            raise ConnectionError("Please connect to C* before invoking this method")
        with self.lock:
            if tables:
                for table in tables:
                    execute(f"DROP TABLE IF EXISTS {table.lower()}")
            if keyspace:
                metadata = self.metadata(keyspace=keyspace.lower())
                tables = metadata.keyspaces.get(keyspace.lower(), {})
                for table in tables.keys():
                    execute(f"DROP TABLE IF EXISTS {keyspace}.{table}")
                execute(f"DROP KEYSPACE IF EXISTS {keyspace}")
            else:
                for keyspace in self.keyspaces:
                    entities = self.keyspaces[keyspace.lower()]
                    for entity in entities.keys():
                        execute(f"DROP TABLE IF EXISTS {keyspace}.{entity.table()}")
                    execute(f"DROP KEYSPACE IF EXISTS {keyspace}")
        self.clear()


"""
Table:
A facade that translates Model, Expando, Array, SortedSet objects to/from C* using
the Unit of Work pattern. The UoW is built using the differ package which tracks changes
to each entity, and builds a list of changes to be executed in a single batch, an accord transaction
, or as a series of independent queries, depending on the `batch` and `accord` parameters.

This class/object is only for internal use. Users should use `Entity` objects,
`Expando`, `Array`, `SortedSet` objects or the Fluent API, and `Session` to 
interact with C*.
"""


class Table(object):
    """Implementation proxy for Entity objects"""

    def __init__(self, entity: Entity, batch=True, accord=True, version=False):
        """Setup the internal state of the Table object"""
        from cqlalchemy.history import capture
        from cqlalchemy.core.models import CounterEntity

        if not issubclass(entity, Entity):
            raise SchemaError("Provide a subclass of `Entity` to Table")
        if issubclass(entity, CounterEntity):
            raise SchemaError(
                "`Counter` entities not supported, use `CounterTable` instead."
            )

        self.batch = batch
        self.accord = accord
        self.key = Key.create(entity)
        self.properties = fields(entity, CqlProperty)
        self.entity = entity
        self.created = False
        if version:
            subscribe(Event.AFTER_BATCH, capture)
            subscribe(Event.AFTER_EXECUTE, capture)
            subscribe(Event.AFTER_TRANSACTION, capture)
            subscribe(Event.AFTER_REMOVE, capture)

    def refresh(self):
        """Synchronizes Schema of the entity with our internal schema"""
        if not self.created:
            if not Schema.exists(self.entity):
                Schema.put(self.entity)
                Schema.create(self.entity)
                self.created = True
            else:
                self.created = True

    def keyspace(self):
        """Returns the configured keyspace of the entity"""
        return self.entity.keyspace()

    def insert(self, instance: Entity, unique: bool = False):
        """Insert a new Entity into C*"""
        from cqlalchemy.history import Edit
        self.refresh()

        if instance.saved():
            raise BadValueError("Expecting a new Entity, not an already saved one.")
        if not changed(instance):
            raise BadValueError("There is no modification to save.")

        instance.validate()
        query = "INSERT INTO {table} ({columns}) VALUES ({values}){unique}{ttl};"
        unique = " IF NOT EXISTS" if unique else ""
        expire = instance.expire
        ttl = " USING TTL {expire}".format(expire=expire) if expire else ""

        columns, values = [], []
        # Ignore the differ for INSERT queries, as we are performing direct conversions.
        attributes = self.properties
        for name in attributes:
            property = attributes.get(name)
            if not property.saveable():
                continue
            value = getattr(instance, name, None)
            if value:
                value = property.convert(instance, value)
                columns.append(name)
                values.append(value)

        if unique:  # Use a LWT, supported by Paxos for this DML query.
            query = query.format(
                keyspace=instance.keyspace(),
                table=instance.table(),
                unique=unique,
                columns=", ".join(columns),
                values=", ".join(values),
                ttl=ttl,
            )
        else:
            query = query.format(
                keyspace=instance.keyspace(),
                table=instance.table(),
                unique=unique,
                columns=", ".join(columns),
                values=", ".join(values),
                ttl=ttl,
            )
        self.save(instance,[query,], change=Edit.INSERT)

    def update(self, instance: Entity):
        """Update an Entity that already exists in C*"""
        from cqlalchemy.history import Edit

        self.refresh()
        if not instance.saved():
            raise BadValueError(
                "Your Entity has not been saved before, please use the `insert` function instead"
            )

        instance.validate()
        if changed(instance):
            trackables = dict()
            trackables[instance] = None

            for attribute in self.properties:
                value = getattr(instance, attribute, None)
                if value and trackable(value):
                    trackables[value] = attribute

            operations = []
            deletion = [
                Action.LDELETE,
                Action.ODELETE,
                Action.MDELETE,
            ]
            for var in trackables:
                name = trackables[var]
                for operation in changes(var):
                    if not operation.name:
                        operation.name = name
                    operations.append(operation)
            self._validate_(operations)
            queries = []
            # Sort them by time.
            operations = sorted(operations, key=lambda op: op.timestamp)
            updates = [operation for operation in operations if operation.code not in deletion]
            deletes = [operation for operation in operations if operation.code in deletion]
            if updates:
                query = self._update_(instance, updates)
                queries.append(query)
            if deletes:
                for operation in deletes:
                    query = self._delete_(instance, operation)
                    queries.append(query)
            self.save(instance, queries, change=Edit.UPDATE)

    def upsert(self, instance: Entity, condition: Predicate = None, exists:bool=False):
        """Update an Entity that already exists in C* directly without reading it"""
        from cqlalchemy.history import Edit

        self.refresh()
        if condition and exists:
            raise ValueError(
                "Cannot allow `Predicate` and `IF EXISTS` at the same time"
            )
        if instance.saved():
            raise BadValueError("Expected a new & unsaved Entity")
        if not changed(instance):
            raise BadValueError("There is no modification to save.")

        instance.validate()
        query = "UPDATE {table} {ttl}\n    SET {data}\nWHERE {key}{condition}{conditional};"
        expire = instance.expire
        conditional = " IF EXISTS" if exists else ""
        ttl = " USING TTL {expire}".format(expire=expire) if expire else ""

        condition = str(condition) if condition else ""
        key = self._key_(instance)
        partial_ = partial(self._screen_, parent=instance)
        operations = [operation for operation in added(instance, screen=partial_)]
        self._validate_(operations)

        assignments = []
        attributes = self.properties
        # Ignore the differ for INSERT/UPSERT queries, as we are performing direct conversions.
        for operation in operations:
            property = attributes.get(operation.name)
            if not property.saveable() or (hasattr(property, "key") and property.key):
                continue
            value = property.convert(instance, operation.value)
            expr = f"{operation.name} = {value},"
            assignments.append(expr)

        data = "\n".join(assignments)
        data = data.strip(",")
        query = query.format(
            table=instance.table(),
            ttl=ttl,
            data=data,
            key=key,
            condition=condition,
            conditional=conditional,
        )
        self.save(instance,[query,], change=Edit.UPSERT)

    def delete(self, instance: Union[Entity, Pointer]):
        """Delete an entire instance/row of an Entity from C*"""
        from cqlalchemy.history import Edit

        self.refresh()
        if isinstance(instance, Entity) and not instance.saved():
            raise BadValueError("Your Entity has not been saved before")
        try:
            query = "DELETE FROM {table} WHERE {key};"
            query = query.format(table=self.entity.table(), key=self._key_(instance))
            self.remove(instance, query, change=Edit.DELETE)
        except Exception as e:
            raise e

    def read(self, key: Pointer):
        """Fetches an Entity from C* and returns it"""
        if not isinstance(key, Pointer):
            raise BadValueError("`Pointer` object expected")
        self.refresh()
        instance = SelectQuery(self.entity).where(**key.parts).get()
        return instance

    def truncate(self):
        """Deletes all the rows in this Table"""
        self.refresh()
        try:
            query = "TRUNCATE {table}".format(table=self.entity.table())
            return execute(query, keyspace=self.keyspace())
        except Exception as e:
            raise e

    def save(self, instance, operations, change=None):
        """Save with a batch or a transaction"""
        try:
            atom = Atom.get()
            if atom:
                if debug():
                    print("*" * 100)
                    print("Joining Transaction: %s" % atom)
                    print("*" * 100)
                if not self.accord:
                    raise CqlQueryException("Transaction not allowed, because Accord is disabled on this Entity")
                return self.save_with_transaction(atom, instance, operations, change)
                
            batch = Batch.get()
            if batch:
                if not self.batch:
                    raise CqlQueryException("Batch not allowed, because Batch is disabled on this Entity")
                return self.save_with_batch(instance, operations, change, batch) 

            group = Group.get() 
            if group:
                for query in operations:
                    group.add(query)
                return 
            # If we got here, it means there is no open Atom|Batch|Group context
            # This means we can create our own batch and save the object, if it supports batches, or save it directly. 
            if self.batch:
                # Create our own batch by passing batch=None
                return self.save_with_batch(instance, operations, change, batch=None)
            else:
                return self.save_without_batch(instance, operations, change)
        except Exception as e:
            raise e

    def save_without_batch(self, instance, operations, change=None):
        """Executes queries for this table/instance serially and synchronously."""
        try:
            for query in operations:
                execute(query, self.keyspace())
            propagate(Event.AFTER_EXECUTE, sender=self, batch=None, entity=instance, edit=change)
            propagate(Event.BEFORE_SAVE, sender=self, batch=None, entity=instance, edit=change)
            commit(instance)
            propagate(Event.AFTER_SAVE, sender=self, batch=None, entity=instance, edit=change)
        except Exception as e:
            raise e

    def save_with_batch(self, instance, operations, change=None, batch=None):
        """Executes queries for this Table, and related objects using a Batch"""
        try:
            isolated, context = False, batch
            if not context and self.batch:
                context = Batch.create(BatchType.Normal, self.keyspace())
                isolated = True
            # If there is an already existing open batch, simply join it.
            if context:
                for query in operations:
                    context.add(query)
                # Allow listeners to join the batch by firing pre-batch events.
                propagate(
                    Event.BEFORE_SAVE, 
                    sender=self, 
                    entity=instance, 
                    batch=context, 
                    edit=change
                )
                # These will be executed after the batch has closed.
                after_batch = partial(
                    propagate, 
                    Event.AFTER_BATCH, 
                    sender=self, 
                    batch=context, 
                    entity=instance, 
                    edit=change
                )
                deferred_commit = partial(commit, instance)
                after_save = partial(
                    propagate, 
                    Event.AFTER_SAVE, 
                    sender=self, 
                    batch=context, 
                    entity=instance, 
                    edit=change
                )
                context.after([after_batch, deferred_commit, after_save])
                context.include(instance)

                if isolated: # This is our batch, so we can execute it immediately.
                    context.execute()
        except Exception as e:
            raise e
        finally:
            if isolated: # This is our batch, so we can close it.
                context.unset()

    def save_with_transaction(self, atom, instance, operations, change=None):
        """Executes queries for this Table, and related objects using a Transaction"""
        # If the Table does not support transactions, or there is no open transaction, use a batch instead.
        try:
            if atom and atom.open:
                for query in operations:
                    atom.add(query)
                
                # Allow listeners to join the transaction by firing pre-transaction events.
                propagate(
                    Event.BEFORE_SAVE, 
                    sender=self, 
                    entity=instance, 
                    atom=atom, 
                    edit=change
                )
                propagate(
                    Event.BEFORE_TRANSACTION, 
                    sender=self, 
                    entity=instance, 
                    atom=atom, 
                    edit=change
                )
                after_transaction = partial(
                    propagate, 
                    Event.AFTER_TRANSACTION, 
                    sender=self, 
                    atom=atom, 
                    entity=instance, 
                    edit=change
                )
                deferred_commit = partial(commit, instance)
                after_save = partial(
                    propagate, 
                    Event.AFTER_SAVE, 
                    sender=self, 
                    entity=instance, 
                    atom=atom, 
                    edit=change
                )
                atom.after([after_transaction, deferred_commit, after_save])
                atom.invalidate(instance)
                # The owner of the transaction/or context manager will commit the transaction
            else:
                raise CqlQueryException("No open transaction provided")
        except Exception as e:
            raise e
    
    def remove(self, pointer, query, change=None):
        """Remove with a transaction or a batch"""
        try:
            atom = Atom.get()
            if atom:
                self.remove_with_transaction(atom, pointer, query, change)
            else:
                self.remove_with_batch(pointer, query, change)
        except Exception as e:
            raise e

    def remove_with_transaction(self, atom, pointer, query, change=None):
        """Perform a removal using a Transaction, falling back to a Batch"""
        try:
            if atom and atom.open:
                atom.add(query)
                propagate(Event.BEFORE_REMOVE, sender=self, key=pointer, atom=atom, edit=change)
                propagate(Event.BEFORE_TRANSACTION, sender=self, key=pointer, atom=atom, edit=change)
                after_remove = partial(
                    propagate, Event.AFTER_REMOVE, sender=self, 
                    atom=atom, key=pointer, edit=change
                )
                after_transaction = partial(
                    propagate, Event.AFTER_TRANSACTION, sender=self, 
                    atom=atom, key=pointer, edit=change
                )
                atom.after([after_remove, after_transaction])
                atom.invalidate(pointer)
            else:
                raise CqlQueryException("No open transaction provided")
        except Exception as e:
            raise e

    def remove_with_batch(self, pointer, query, change=None):
        """Perform a removal using a Batch"""
        try:
            context = Batch.get()
            if context:
                context.add(query)
                propagate(Event.BEFORE_REMOVE, sender=self, key=pointer, batch=context, edit=change)
                after_remove = partial(propagate, Event.AFTER_REMOVE, sender=self, batch=context, key=pointer, edit=change)
                context.after([after_remove])
                context.include(pointer)
            else:
                execute(query, self.keyspace())
                propagate(Event.AFTER_REMOVE, sender=self, key=pointer, batch=None, edit=change)
        except Exception as e:
            raise e

    def _screen_(self, operation, parent):
        """Accept only change operations for this entity"""
        return operation.parent == parent

    def _validate_(self, operations):
        qualified = []
        for op in operations:
            descriptor = self.properties.get(op.name)
            if descriptor.key or descriptor.primary:
                continue
            else:
                qualified.append(op)

        if len(qualified) == 1:
            first = qualified[0]
            descriptor = self.properties.get(first.name)
            if descriptor.static:
                raise IsolatedStaticFieldException(
                    f"Cannot update static field `{op.name}` in isolation"
                )

    def _key_(self, instance: Union[Entity, Pointer]):
        """Internal function used to generate the 'key component' of an update query"""
        pointer = instance.key if isinstance(instance, Entity) else instance
        if pointer is None:
            raise IllegalStateException(f"The `Pointer` for {instance} cannot be None")

        expression = ""
        started = False
        for name, value in pointer.parts.items():
            part = " {name}={value}"
            prop = self.properties.get(name)
            component = part.format(name=name, value=prop.convert(instance, value))
            if started:
                expression = expression + " AND"
            expression = expression + component
            started = True
        return expression

    def _update_(self, instance, operations: Iterable["Operation"]):
        """Generates the appropriate update/assignment expression and query"""
        from cqlalchemy.core.types import List

        update_format = """UPDATE {table} {ttl}\n\tSET {assignment}\nWHERE {key}{conditions};"""
        expressions = []
        for operation in operations:
            # 0. Skip Key Related Operations in the SET part of the query.
            descriptor = self.properties.get(operation.name)
            if descriptor.key or descriptor.primary:
                continue
            expr = None
            # 1. Deal with direct changes on top level attributes which are descriptors
            changes = (Action.OCHANGE, Action.OSET)
            if operation.parent == instance:
                if operation.name in self.properties and operation.code in changes:
                    descriptor = self.properties.get(operation.name)
                    value = descriptor.convert(instance, operation.value)
                    expr = "{0}={1}".format(operation.name, value)
                else:
                    pass  # Ignore changes from non-descriptors in the Entity.
            elif operation.parent != instance:
                if operation.name in self.properties and operation.code not in changes:
                    match operation.code:
                        case Action.MADD:
                            descriptor = self.properties.get(operation.name)
                            T, V = descriptor.converter
                            key = T.convert(instance, operation.key)
                            value = V.convert(instance, operation.value)
                            expr = "{0}[{1}] = {2}".format(operation.name, key, value)

                        case Action.SADD:
                            descriptor = self.properties.get(operation.name)
                            value = operation.value
                            if not isinstance(value, set):
                                value = {
                                    value,
                                }
                            value = descriptor.convert(instance, value)
                            expr = "{name} = {name} + {value}".format(
                                name=operation.name, value=value
                            )

                        case Action.SDELETE:
                            descriptor = self.properties.get(operation.name)
                            value = operation.value
                            if not isinstance(value, set):
                                value = {
                                    value,
                                }
                            value = descriptor.convert(instance, value)
                            expr = "{name} = {name} - {value}".format(
                                name=operation.name, value=value
                            )
                            expression = expr

                        case Action.LAPPEND:
                            descriptor = self.properties.get(operation.name)
                            value = operation.value
                            if not isinstance(value, (list, List)):
                                value = [
                                    value,
                                ]
                            value = descriptor.convert(instance, value)
                            expr = "{name} = {name} + {value}".format(
                                name=operation.name, value=value
                            )

                        case Action.LPREPEND:
                            descriptor = self.properties.get(operation.name)
                            value = operation.value
                            if not isinstance(value, (list, List)):
                                value = [
                                    value,
                                ]
                            value = descriptor.convert(instance, value)
                            expr = "{name} = {value} + {name}".format(
                                name=operation.name, value=value
                            )

                        case Action.LINSERT:
                            descriptor = self.properties.get(operation.name)
                            T = descriptor.converter
                            value = T.convert(instance, operation.value)
                            expr = "{name}[{index}] = {value}".format(
                                name=operation.name, index=operation.index, value=value
                            )

                        case _:
                            raise IllegalStateException(
                                "Unsupported Action: %s" % operation.code
                            )
            else:
                raise IllegalStateException("Operations from Unexpected Objects")
            expressions.append(expr)

        expression = ", ".join(expressions)
        table = instance.table()
        expire = operation.ttl if operation.ttl else instance.expire
        ttl = " USING TTL {expire}".format(expire=expire) if expire else ""
        conditions = " %s" % str(operation.condition) if operation.condition else ""
        key = self._key_(instance)
        query = update_format.format(
            table=table, ttl=ttl, assignment=expression, key=key, conditions=conditions
        )
        return query

    def _delete_(self, instance, operation):
        """Generates the appropriate DML for removing a member of @instance"""
        delete_format = "DELETE {expression} FROM {table} WHERE {key}{conditions};"
        table = self.entity.table()

        expression = None
        match operation.code:
            case Action.LDELETE:
                expr = "{name}[{index}]".format(
                    name=operation.name, index=operation.index
                )
                expression = expr
            case Action.ODELETE:
                expr = "{name}".format(name=operation.name)
                expression = expr
            case Action.MDELETE:
                descriptor = self.properties.get(operation.name)
                T = descriptor.converter[0]
                key = T.convert(instance, operation.key)
                expr = "{name}[{key}]".format(name=operation.name, key=key)
                expression = expr
            case _:
                raise IllegalStateException(
                    "Received an Unsupported Action: %s" % operation.code
                )

        key = self._key_(instance)
        conditions = " %s" % str(operation.condition) if operation.condition else ""
        return delete_format.format(
            expression=expression, table=table, key=key, conditions=conditions
        )


"""
CounterTable:
Knows how to persist/read CounterModel objects to/from C*. 
"""


class CounterTable(object):
    """Implementation proxy for Counter Tables"""

    def __init__(self, entity: Entity):
        """Setup the internal state of the Table object"""
        self.key = Key.create(entity)
        self.entity = entity
        self.created = False
        self.properties = fields(entity, CqlProperty)

    def refresh(self):
        """Synchronizes Schema of the entity with our internal schema"""
        if not self.created and not Schema.exists(self.entity):
            # This only creates/syncs the table the first time we see it.
            stump = self.entity()
            Schema.create(stump)
            self.created = True

    def keyspace(self):
        """Returns the configured keyspace of the entity"""
        return self.entity.keyspace()

    def save(self, instance: Entity, unique: bool = False):
        """Update an Entity that already exists in C*"""
        self.refresh()
        instance.validate()
        if changed(instance):
            query = """UPDATE {table}\n    SET {assignments}\nWHERE {key}{conditions};"""
            parts = []
            for operation in changes(instance):
                property = self.properties.get(operation.name)
                if operation.code == Action.CDECR:
                    name = operation.name
                    value = property.convert(self.entity, operation.value)
                    part = f"{name} = {name} - {value},"
                    parts.append(part)
                elif operation.code == Action.CINCR:
                    name = operation.name
                    value = property.convert(self.entity, operation.value)
                    part = f"{name} = {name} + {value},"
                    parts.append(part)
                else:
                    raise BadValueError(
                        "Only Counter related operations can be serialized here."
                    )

            assignment = "\n".join(parts)
            assignment = assignment.strip(",")
            conditions = " IF NOT EXISTS" if unique else ""
            key = self._key_(instance)
            table = self.entity.table()
            query = query.format(
                table=table, assignments=assignment, key=key, conditions=conditions
            )
            queries = [
                query,
            ]
            self._persist_(instance, queries)

    def read(self, key: Pointer):
        """Fetches an Entity from C* and returns it"""
        if not isinstance(key, Pointer):
            raise BadValueError(
                "You can only read from a Table using a `Pointer` object"
            )
        self.refresh()
        instance = SelectQuery(self.entity).where(**key.parts).get()
        return instance

    def _persist_(self, instance, operations):
        """Executes queries for this Table, and related objects using a Batch"""
        try:
            isolated = False
            context = Batch.get()
            if not context:
                context = Batch.create(BatchType.Counter, keyspace=self.keyspace())
                isolated = True
            else:
                if context.type != BatchType.Counter:
                    raise IllegalStateException(
                        "BatchType Error: Cannot add `counter` queries to a non-counter batch."
                    )
            for query in operations:
                context.add(query)
            # Allow listeners to join the batch.
            propagate(Event.BEFORE_SAVE, instance, batch=context)
            deferred_commit = partial(commit, instance)
            deferred_notify = partial(propagate, Event.AFTER_SAVE, instance)
            context.after([deferred_commit, deferred_notify])
            if isolated:
                context.execute()
        except Exception as e:
            raise e
        finally:
            if isolated:
                context.unset()

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
