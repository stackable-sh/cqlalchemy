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


import time
from typing import Unpack, List
from collections import OrderedDict

import schema
import black

from cqlalchemy.core.models import Key, CqlProperty
from cqlalchemy.core.models import Index as IndexEnum
from cqlalchemy.revisions import typing
from cqlalchemy.connection.cql import execute
from cqlalchemy.connection.table import Metadata, SchemaError


__all__ = [
    "Operation",
    "OperationError",
    "Schema",
    "Keyspace",
    "Table",
    "Drop",
    "Column",
    "Index",
    "Rename",
    "Truncate",
    "Field"
]


DEFAULT_REPLICAS  = 3


class OperationError(Exception):
    """Base class for a Operation related exceptions"""
    pass 


"""
Operation:
This is the base class of all DDL operations in C*. Please find the different supported 
operations below.
"""
class Operation(object):
    """A schema alteration for C*"""

    def __init__(self, **keywords) -> None:
        self.context = {}
        for name, value in keywords.items():
            self.context[name] = value 
    
    def validate(self) -> bool:
        """Check C* to see if this Operation succeeded"""
        return True 
    
    def execute(self):
        """Runs the operation against C*"""
        raise NotImplementedError("Implemented in a sub class")

    def __repr__(self) -> str:
        name = self.__class__.__name__
        part = ", ".join(f"{k} = {v!r}" for k, v in self.context.items())
        return f"{name}({part})"

"""
Schema
A Noop that prints the current schema to the console.

```python
operation = Schema(keyspace="keyspace")
```

"""
class Schema(Operation):
    """A Noop that prints the current schema to the console"""
    executed: bool = False 

    def validate(self) -> bool:
        """Checks whether the Keyspace has been created"""
        return self.executed

    def execute(self) -> bool:
        """Creates a new keyspace if it does not already exist"""
        metadata = Metadata.fetch(self.context.get("keyspace"))
        output = repr(metadata)
        formatted = black.format_str(output, mode=black.Mode(line_length=88))
        print(formatted)
        self.executed = True


"""
Keyspace
An Operation that creates a Keyspace in C*

```python
Keyspace(
    name = "Test", 
    options = {
        "replication" : {"NetworkTopologyStrategy" : 5}
    }
)
```
"""
class Keyspace(Operation):
    """Creates a new keyspace"""

    def validate(self) -> bool:
        """Checks whether the Keyspace has been created"""
        while True:
            keyspace = self.context.get("name")
            metadata = Metadata.fetch(keyspace)
            if keyspace in metadata.keyspaces:
                return True 
            time.sleep(0.5)

    def execute(self) -> bool:
        """Creates a new keyspace if it does not already exist"""
        try:
            query = "CREATE KEYSPACE IF NOT EXISTS {keyspace} WITH REPLICATION = {replication} AND DURABLE_WRITES = {durable_writes};"
            keyspace = self.context.get("name")
            options = self.context.get("options", {})
            options = {name.lower() : value for name, value in options.items()}

            durability = options.get("durable_writes", True)
            if "replication" not in options:
                strategy = {"NetworkTopologyStrategy" : DEFAULT_REPLICAS}
            else:
                strategy = options.get("replication")

            validation = schema.Schema(
                schema.Or(
                    {"NetworkTopologyStrategy": int},
                    {"NetworkTopologyStrategy": {str: int}},
                    {"SimpleStrategy": int},
                )
            )
            if not validation.is_valid(strategy):
                raise ValueError(f"Invalid replication strategy {strategy}")
            if schema.Schema({"NetworkTopologyStrategy": int}).is_valid(strategy):
                value = strategy["NetworkTopologyStrategy"]
                replication = f"{{'class' : 'NetworkTopologyStrategy', 'replication_factor' : '{value}'}}"
            elif schema.Schema({"NetworkTopologyStrategy": {str: int}}).is_valid(strategy):
                centres = strategy["NetworkTopologyStrategy"]
                part = ", ".join(
                    [f"'{k}'" + ":" + f"'{v}'" for k, v in list(centres.items())]
                )
                replication = f"{{'class' : 'NetworkTopologyStrategy', {part}}}"
            elif schema.Schema({"SimpleStrategy": int}).is_valid(strategy):
                value = strategy["SimpleStrategy"]
                replication = (
                    f"{{'class' : 'SimpleStrategy', 'replication_factor' : '{value}'}}"
                )
            query = query.format(keyspace=keyspace, replication=replication, durable_writes=durability)
            execute(query)
        except KeyError as error:
            raise OperationError("Invalid Keyspace Context: %s caused error %s" % (self.context, error))




"""
Table
An operation that creates a Cassandra Table in a specified keyspace.

```python

# Table with a single primary key

operation = Table(
    keyspace = "Test",
    name = "Person",
    columns = [
        Field(name="id", type="uuid", primary=True),
    ]
)

# Table with a primary key and multiple clustering keys, with expiry and comments

operation = Table(
    keyspace = "Test",
    name = "Person",
    columns = [
        Field(name="id", type="uuid", primary=True),
        Field(name="created", key=True, type="timestamp", order="DESC"),
        Field(name="name", type="text", index=True),
        Field(name="surname", type="text"), 
    ],
    expires = minutes(10),
    comment="The basic model for a user account",
)

# Table also works with Descriptors 

operation = Table(
    keyspace = "Test",
    name = "Person",
    columns = [
        Field(name="id", type=UUID, primary=True),
        Field(name="username", type=String, key=True),
        Field(name="friends", type=List(UUID), index=True),
    ]
)

```
"""

class Field(object):
    """An object that represents a field in a Table"""

    def __init__(self, **keywords: Unpack[typing.FieldDict]):
        self.name = keywords.get("name")
        self.type = keywords.get("type")
        self.primary = keywords.get("primary")
        self.key = keywords.get("key")
        self.composite = keywords.get("composite")
        self.order = keywords.get("order")
        self.static = keywords.get("static")
        self.index = keywords.get("index")
        self.context = {}
        for name, value in keywords.items():
            self.context[name] = value 

    def __repr__(self) -> str:
        name = self.__class__.__name__
        part = ", ".join(f"{k} = {v!r}" for k, v in self.context.items())
        return f"{name}({part})"


class Table(Operation):
    """Creates a Table & Indexes in C* Idempotently"""

    def __init__(self, **keywords: Unpack[typing.TableDict]):
        super().__init__(**keywords)

    def validate(self) -> bool:
        """Checks whether the Table has been created"""
        table = self.context.get("name")
        keyspace = self.context.get("keyspace")
        columns = self.context.get("columns", [])
        indexes = [field.name for field in columns if field.index]
        table_created, indexes_created = False, False
        while True:
            metadata = Metadata.fetch(keyspace)
            group = metadata.keyspaces.get(keyspace, {})
            if table.lower() in group:
                table_created = True
                break
            else:
                time.sleep(0.5)
        while True:
            metadata = Metadata.fetch(keyspace)
            results = []
            for name in indexes:
                indexes = metadata.indexes[keyspace][table.lower()]
                identifier = Index.name(table, name)
                if identifier not in indexes:
                    results.append(False)
                else:
                    results.append(True)
            if all(results):
                indexes_created = True
                break
            else:
                time.sleep(0.5)
        return table_created and indexes_created

    def execute(self) -> bool:
        """Creates a new keyspace if it does not already exist"""
        try:
            columns_validator = schema.Schema([Field,])
            keyspace = self.context.get("keyspace")
            table = self.context.get("name")
            columns = self.context.get("columns")
            columns = columns_validator.validate(columns)

            # Create a Key Object  
            primary, others, order, indexes = [], [], [], []
            for field in columns:
                if field.order:
                    order.append((field.name, field.order))
                if field.primary:
                    primary.append(field.name) 
                    if field.composite:
                        primary.extend(field.composite)
                if field.key:
                    others.append(field.name) 
                if field.index:
                    indexes.append(field) 
            if len(primary) == 0:
                raise ValueError("Specify a primary key.")
            if len(primary) == 1:
                primary = primary[0]
            else:
                primary = tuple(primary)
            key = Key(keyspace=keyspace, table=table, primary=primary, others=others)
            self.create_table(
                keyspace=keyspace,
                table=table,
                key=key,
                columns=columns,
                accord=self.context.get("accord", True),
                expires=self.context.get("expires", 0),
                comment=self.context.get("comment", ""),
            )
            self.create_indexes(keyspace=keyspace, table=table, columns=indexes)
        except KeyError as error:
            raise OperationError("Invalid Table Context: %s caused error %s" % (self.context, error))
        except Exception as e:
            raise OperationError(f"Failed to create table: {self.context} caused error {e}")

    def create_table(
            self,
            keyspace:str,
            table:str,
            key: Key,
            columns: List[Field],
            accord: bool = True,
            expires: int = 0,
            comment: str = "",
        ) -> bool:
        """Creates a Table in C*, will create the Table and new columns"""
        # Handle Columns.
        fields, attributes = [], {}

        for field in columns:
            name = field.name.lower()
            attributes[field.name] = field
            if isinstance(field.type, str):
                ctype = field.type
            elif isinstance(field.type, CqlProperty) or issubclass(field.type, CqlProperty):
                ctype = field.type.ctype
            else:                                                                                                                                                                                            
                raise ValueError(f"Invalid Field Type: {field.type}")
            static = "static" if field.static else ""
            part = f"{name} {ctype} {static}"
            fields.append(part.strip())

        # Handle Primary Key Information
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

        # Handle Clustering Information
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

        # Handle Transactional Mode
        mode = "off" if not accord else "full"
        fields = ", ".join(fields)
        query = """
        CREATE TABLE {table} (
            {fields},
            PRIMARY KEY ({key})
        ) 
        WITH default_time_to_live = {ttl}{clustering}
        AND transactional_mode = '{mode}'
        AND caching = {{'keys' : 'ALL', 'rows_per_partition' : 'ALL'}}
        AND comment = '{comment}';
        """
        query = query.format(
            table=table,
            fields=fields,
            key=part,
            clustering=clustering,
            ttl=expires,
            mode=mode,
            comment=comment,
        )
        execute(query, keyspace=keyspace)

    def create_indexes(self, keyspace:str, table:str, columns: List[Field]):
        """Idempotently builds the indexes for a given table/columns"""
        queries = []
        for field in columns:
            name = field.name.lower()
            if field.index:
                flag, query = None, None
                identifier = Index.name(table=table, name=name)
                if isinstance(field.index, bool):
                    flag = IndexEnum.Default
                else:
                    flag = field.index
                # Index the Property on C*
                ctype = field.type if isinstance(field.type, str) else field.type.ctype
                match flag:
                    case IndexEnum.Default:
                        if "map" in ctype or "list" in ctype or "set" in ctype:
                            raise ValueError("You cannot use Index.Default on a Collection")
                        else:
                            query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}({name});"
                    case IndexEnum.All:
                        if "map" in ctype:
                            query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(ENTRIES({name}));"
                        elif "list" in ctype or "set" in ctype:
                            query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(VALUES({name}));"
                    case IndexEnum.Keys:
                        if "map" in ctype:
                            query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(KEYS({name}));"
                        else:
                            raise SchemaError(
                                "You can only index the KEYS of a Map<T,V> "
                            )
                    case IndexEnum.Values:
                        if "map" in ctype or "list" in ctype or "set" in ctype:
                            query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(VALUES({name}));"
                        else:
                            raise SchemaError(
                                "You can only index the KEYS of a Map<T,V>, Set<T>, or List<T>"
                            )
                queries.append(query)
        for query in queries:
            execute(query, keyspace=keyspace)


"""
Column:
Adds a new column to an existing Table in C*

```python
op = Column(table="Person", name="age", type="int")
op = Column(table="Person", name="age", type=String)
op = Column(table="Person", name="created", type=DateTime, static=True)
```
"""
class Column(Operation):
    """Creates a Column in C*"""

    def __init__(self, **keywords: Unpack[typing.ColumnDict]):
        super().__init__(**keywords)

    def validate(self) -> bool:
        """Checks whether the column has been created"""
        while True:
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            column = self.context.get("name")

            metadata = Metadata.fetch(keyspace)
            group = metadata.keyspaces.get(keyspace.lower(), {})
            columns = group.get(table.lower(), {})
            if column in columns:
                return True
            else:
                time.sleep(0.5)

    def execute(self) -> bool:
        """Creates a new keyspace if it does not already exist"""
        try:
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            column = self.context.get("name")
            type = self.context.get("type")
            if isinstance(type, str):
                ctype = type 
            elif isinstance(type, CqlProperty) or issubclass(type, CqlProperty):
                ctype = type.ctype
            else:
                raise SchemaError(f"Invalid Column Type: {type}")
            static = "static" if self.context.get("static") else ""
            query = f"ALTER TABLE IF EXISTS {table} ADD {column} {ctype} {static};"
            execute(query, keyspace=keyspace)
        except KeyError as error:
            raise OperationError("Invalid Column Context: %s caused error %s" % (self.context, error))

"""
Index

```python
operation = Index(keyspace="Test", table="Person", column="username")
```
"""
class Index(Operation):
    """Creates an Index in C*"""

    def __init__(self, **keywords: Unpack[typing.IndexDict]):
        super().__init__(**keywords)
    
    def validate(self) -> bool:
        """Checks whether the index has been created"""
        keyspace = self.context.get("keyspace")
        table = self.context.get("table")
        if self.context.get("name", None):
            identifier = self.context.get("name")
        else:
            identifier = self.name(table, self.context.get("column"))
        while True:
            metadata = Metadata.fetch(keyspace)
            indexes = metadata.indexes[keyspace][table.lower()]
            if identifier in indexes:
                return True
            else:
                time.sleep(0.5)

    @classmethod
    def name(cls, table:str, name:str):
        """Cqlalchemy default name for an index"""
        return "index_{0}_{1}".format(table.lower(), name.lower())

    def execute(self) -> bool:
        """Indexes a column in C*"""
        try:
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            column = self.context.get("column")
            category = self.context.get("type", IndexEnum.Default)

            if self.context.get("name", None):
                identifier = self.context.get("name")
            else:
                identifier = self.name(table, column)
            if category == IndexEnum.Default:
                query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}({column});"
            elif category == IndexEnum.Keys:
                query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(KEYS({column}));"
            elif category == IndexEnum.Values:
                query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(VALUES({column}));"
            elif category == IndexEnum.All:
                query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(ENTRIES({column}));"
            else: 
                raise OperationError("Please specify a valid Index category")
            execute(query, keyspace=keyspace)
        except KeyError as error:
            raise OperationError("Invalid Index Context: %s caused error %s" % (self.context, error))

"""
Drop
Allows you to Drop a Keyspace, Table, Column or Index

```python
operation = Drop(target="Column", keyspace="Test", table="Person", column="date")
```
"""
class Drop(Operation):
    """Allows you to Drop a Keyspace, Table, Column or Index"""
    Keyspace, Table, Column, Index = "Keyspace", "Table", "Column", "Index"

    def __init__(self, **keywords: Unpack[typing.DropDict]):
        super().__init__(**keywords)

    def validate(self) -> bool:
        """Checks whether the index has been created"""
        keyspace = self.context.get("keyspace")
        target = self.context.get("target")
        while True:
            metadata = Metadata.fetch(keyspace)
            succeeded = False 
            if target.title() == Drop.Keyspace:
                print(metadata.keyspaces)
                succeeded = keyspace.lower() not in metadata.keyspaces
            elif target.title() == Drop.Table:
                table = self.context.get("table")
                tables = metadata.keyspaces.get(keyspace, {})
                succeeded = table.lower() not in tables
            elif target.title() == Drop.Column:
                table = self.context.get("table")
                column = self.context.get("column")
                tables = metadata.keyspaces.get(keyspace, {})
                table = tables.get(table.lower(), {})
                succeeded = column.lower() not in table
            elif target.title() == Drop.Index:
                table = self.context.get("table")
                name = self.context.get("index")
                identifier = Index.name(table, name)
                tables = metadata.indexes.get(keyspace, {})
                table = tables.get(table, {})
                succeeded = identifier.lower() not in table
            
            if succeeded:
                return True
            else:
                time.sleep(0.5)
        
    def execute(self) -> bool:
        """Drops a column in C*"""
        try:
            target = self.context.get("target")
            keyspace = self.context.get("keyspace")
            if target.title() == Drop.Keyspace:
                query = f"DROP KEYSPACE IF EXISTS {keyspace};"
            elif target.title() == Drop.Table:
                table = self.context.get("table")
                query = f"DROP TABLE IF EXISTS {table};"
            elif target.title() == Drop.Column:
                table = self.context.get("table")
                column = self.context.get("column")
                query = f"ALTER TABLE IF EXISTS {table} DROP IF EXISTS {column};"
            elif target.title() == Drop.Index:
                table = self.context.get("table")
                index = self.context.get("index")
                identifier = Index.name(table, index)
                query = f"DROP INDEX IF EXISTS {identifier};"
            else:
                raise OperationError("Please specify a valid Drop category")
            if target.title() == Drop.Keyspace:
                execute(query)
            else:
                execute(query, keyspace=keyspace)
        except KeyError as error:
            raise OperationError("Invalid Drop Context: %s caused error %s" % (self.context, error))




"""
Rename
Allows you to rename a column in C*

```python
operation = Rename(keyspace="Test", table="Person", column="id", to="username")
```
"""
class Rename(Operation):
    """Renames a column in C*"""
    def __init__(self, **keywords: Unpack[typing.RenameDict]):
        super().__init__(**keywords)

    def validate(self) -> bool:
        """Checks whether the column has been renamed"""
        while True: 
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            to = self.context.get("to")

            metadata = Metadata.fetch(keyspace)
            group = metadata.keyspaces.get(keyspace, {})
            columns = group.get(table.lower(), {})
            if to in columns:
                return True
            else:
                time.sleep(0.5)

    def execute(self) -> bool:
        """Renames a column in C*"""
        try:
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            column = self.context.get("column")
            to = self.context.get("to")
            query = f"ALTER TABLE IF EXISTS {table} RENAME IF EXISTS {column} TO {to};"
            execute(query, keyspace=keyspace)
        except KeyError as error:
            raise OperationError("Invalid Rename Context: %s caused error %s" % (self.context, error))


"""
Truncate
Allows you to remove all the rows in a Table

```python
operation = Truncate(keyspace="Test", table="Friends")
```
"""
class Truncate(Operation):
    """Allows you to Truncate a Table"""

    def __init__(self, **keywords: Unpack[typing.TruncateDict]):
        super().__init__(**keywords)

    def validate(self) -> bool:
        """Checks whether the Table has been truncated"""
        return True 
        
    def execute(self) -> bool:
        """Removes all the data in a Table"""
        try:
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            query = f"TRUNCATE {table}"
            execute(query, keyspace=keyspace)
        except KeyError as error:
            raise OperationError("Invalid Truncate Context: %s caused error %s" % (self.context, error))




