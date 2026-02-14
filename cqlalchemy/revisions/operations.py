
import time
import schema

from collections import OrderedDict
from cqlalchemy.connection.cql import execute
from cqlalchemy.connection.table import Metadata


DEFAULT_WAIT_TIME, DEFAULT_REPLICAS  = 30, 5

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
        self.context = OrderedDict()
        for name, value in keywords.items():
            self.context[name] = value 
    
    def validate(self) -> bool:
        """Check C* to see if this Operation succeeded"""
        return True 
    
    def reverse(self):
        """Returns the reverse of this operation"""
        raise NotImplementedError("Implemented in a sub class")
    
    def execute(self):
        """Runs the operation against C*"""
        raise NotImplementedError("Implemented in a sub class")

    def __repr__(self) -> str:
        name = self.__class__.__name__
        context = []
        for name, value in self.context.items():
            if isinstance(value, str):
                name, value = repr(name), repr(value)
                context.append(f"{name}='{value}'")
            else:
                context.append(f"{name}={value}")
        context = ",".join(context)
        return f"{name}({context})"


def wait(function, timeout=10):
    """Loops until @function turns True before we return, we use this to check if Schema changes have been effected"""
    start = time.time()
    end = start + (timeout * 1000)
    while True:
        if time.time() >= end:
            raise OperationError("Specified wait time has elapsed.")
        result = function()
        if result:
            return result 
        else:
            time.sleep(0.1)


"""
Keyspace
An Operation that creates a Keyspace in C*

```python
Keyspace(
    name = "Test", 
    settings = {
        "replication" : {"NetworkTopologyStrategy" : 5}
    }
)
```
"""
class Keyspace(Operation):
    """Creates a new keyspace"""

    def validate(self) -> bool:
        """Checks whether the Keyspace has been created"""
        keyspace = self.context.get("name")
        metadata = Metadata.fetch(keyspace)
        return keyspace in metadata.keyspaces

    def execute(self) -> bool:
        """Creates a new keyspace if it does not already exist"""
        try:
            query = "CREATE KEYSPACE IF NOT EXISTS {keyspace} WITH REPLICATION = {replication} AND DURABLE_WRITES = {durable_writes};"
            keyspace, settings = self.context.get("name"), self.context.get("settings", {})
            settings = {name.lower() : value for name, value in settings.items()}

            durability = settings.get("durable_writes", True)
            if "replication" not in settings:
                strategy = {"NetworkTopologyStrategy" : DEFAULT_REPLICAS}
            else:
                strategy = settings.get("replication")
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
            else:
                raise OperationError("Invalid Keyspace configuration dictionary: %s" % settings)
            
            query = query.format(keyspace=keyspace, replication=replication, durable_writes=durability)
            execute(query)
            wait(self.validate, DEFAULT_WAIT_TIME)
        except KeyError:
            raise OperationError("Invalid Keyspace configuration dictionary: %s" % settings)

    def reverse(self):
        """Returns an operation that deletes a Keyspace if it exists"""
        keyspace = self.context.get("keyspace")
        return Drop(target="Keyspace", keyspace=keyspace, context=self.context)


"""
Table
An operation that creates a Cassandra Table in a specified keyspace.

```python

# Table with a single primary key

operation = Table(
    keyspace = "Test", 
    name = "Person", 
    key = "id",
    columns = [("id", "uuid")], 
)

# Table with a primary key and multiple clustering keys

operation = Table(
    keyspace="Test",
    name="Person",
    columns=[
        ("name", "text"), 
        ("surname", "text"), 
        ("id", "uuid"),
        ("created", "timestamp")
    ],
    key=["id", "created",]
    order=[("created", "DESC",)]
)


# Table with a clustering order, and custom ordering for the partition and clustering keys.

operation = Table(
    keyspace = "Test",
    name = "Person",
    columns = [
        ("name", "text"), 
        ("username", "text"),
        ("surname", "text"), 
        ("id", "uuid"),
        ("host", "uuid",),
        ("created", "timestamp")
    ],
    static = ["host",],
    expires = minutes(10),
    key = [("id", "created"), "username",],
    order = [("created", "DESC",)],
    comment="The basic model for a user account",
)
```
"""
class Table(Operation):
    """Creates a Table in C*"""

    def validate(self) -> bool:
        """Checks whether the Table has been created"""
        table = self.context.get("name")
        keyspace = self.context.get("keyspace")
        metadata = Metadata.fetch(keyspace)
        group = metadata.keyspaces.get(keyspace, {})
        return table in group

    def execute(self) -> bool:
        """Creates a new keyspace if it does not already exist"""
        try:
            columns_validator = [(str, str),]
            keys_validator = [str, schema.Or((str,)) ]
            order_validator = [(str, schema.Or("DESC", "ASC")),]
            static_validator = [str,]
            settings_validator = {
                "caching" : {"keys" : str, "rows_per_partition" : int},
                "read_repair" : str,
                "memtable_flush_period_in_ms" : int,
                "compression" : str,
                "compaction" : {
                    "class" : str, 
                    "enabled" : bool, 
                    "chunk_length_in_kb" : int, 
                    "crc_check_chance" : float, 
                    "compression_level" : int,
                }, 
                "default_time_to_live" : int, 
                "bloom_filter_fp_chance" : float, 
                "gc_grace_seconds" : int, 
                "additional_write_policy" : str, 
                "cdc" : bool, 
                "speculative_retry" : str, 
                "comment" : str, 
            }

            keyspace = self.context.get("keyspace")
            table = self.context.get("name")
            key = self.context.get("key")
            order = self.context.get("order")
            columns = self.context.get("columns")
            settings = self.context.get("settings", {})
            static = self.context.get("static", [])

            query = """
            CREATE TABLE {table} (
                {columns},
                PRIMARY KEY ({key})
            ) {extras}
            """

            # Validate and clean data for use. 
            key = schema.Schema(keys_validator).validate(key)
            columns = schema.Schema(columns_validator).validate(columns)
            static = schema.Schema(static_validator).validate(static)
            order = schema.Schema(order_validator).validate(order)
            configuration = {}
            if settings:
                for name, item in settings.items():
                    name = name.lower()
                    if name in settings_validator:
                        validator = settings_validator.get(name)
                        value = schema.Schema(validator).validate(item)
                        configuration[name] = value 
                
                # Explicitly overwrite the row expiry settin
                expires = self.context.get(
                    "expires", 
                    configuration.get("default_time_to_live", 0)
                )
                configuration["default_time_to_live"] = expires
                
            column_values = []
            for name, value in columns:
                static_column = " static" if name in static else ""
                part = f"{name} {value}{static_column}"
                column_values.append(part)

            key_values = [repr(val) for val in key]
            if not order and not settings:
                extras = ""
            else:
                extras, cluster_order, config_options = "", "", ""
                if order: 
                    part = "CLUSTERING ORDER BY ({val})"
                    variables = []
                    for column, sort in order:
                        token = f"{column} {sort}"
                        variables.append(token)
                    cluster_order = part.format(val=",".join(variables))
                if configuration:
                    part = ""
                    variables = []
                    for name, value in configuration.items():
                        value = repr(value)
                        variables.append(f"{name} = {value}")
                    config_options = " AND".join(variables)
                if cluster_order:
                    extras = f"WITH {cluster_order}"
                if config_options:
                    if extras:
                        extras += f" AND {config_options}"
                    else:
                        extras = f"WITH {config_options}"

            query = query.format(
                table=table,
                columns=",".join(column_values),
                key=",".join(key_values),
                extras=extras
            )
            execute(query, keyspace=keyspace)
            wait(self.validate, DEFAULT_WAIT_TIME)
        except KeyError:
            raise OperationError("Invalid Table keywords: %s" % self.context)
        

    def reverse(self):
        """Returns an operation that deletes a Keyspace if it exists"""
        table = self.context.get("name")
        keyspace = self.context.get("keyspace")
        return Drop(target="Table", keyspace=keyspace, table=table, context=self.context)

"""
Column:
Adds a new column to an existing Table in C*

```python
operation = Column(keyspace="Test", table="Person", name="age", type="int")
```
"""
class Column(Operation):
    """Creates a Column in C*"""

    def validate(self) -> bool:
        """Checks whether the column has been created"""
        keyspace = self.context.get("keyspace")
        table = self.context.get("table")
        column = self.context.get("name")

        metadata = Metadata.fetch(keyspace)
        group = metadata.keyspaces.get(keyspace, {})
        columns = group.get(table, {})
        return column in columns

    def execute(self) -> bool:
        """Creates a new keyspace if it does not already exist"""
        try:
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            column = self.context.get("name")
            ctype = self.context.get("type")
            query = f"ALTER TABLE IF EXISTS {table} ADD {column} {ctype};"
            execute(query, keyspace=keyspace)
            wait(self.validate, DEFAULT_WAIT_TIME)
        except KeyError:
            raise OperationError("Invalid Column Context: %s" % self.context)

    def reverse(self):
        """Returns an Op that removes this column from the schema"""
        column = self.context.get("name")
        table = self.context.get("table")
        keyspace = self.context.get("keyspace")
        return Drop(target="Column", keyspace=keyspace, table=table, column=column, context=self.context)

"""
Rename
Allows you to rename a primary key Column in C*

```python
operation = Rename(keyspace="Test", table="Person", name="id", to="username")
```

"""
class Rename(Operation):
    """Renames a key column in C*"""

    def validate(self) -> bool:
        """Checks whether the column has been renamed"""
        keyspace = self.context.get("keyspace")
        table = self.context.get("table")
        column = self.context.get("to")

        metadata = Metadata.fetch(keyspace)
        group = metadata.keyspaces.get(keyspace, {})
        columns = group.get(table, {})
        return column in columns

    def execute(self) -> bool:
        """Renames a column in C*"""
        try:
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            column = self.context.get("name")
            to = self.context.get("to")
            query = f"ALTER TABLE IF EXISTS {table} RENAME IF EXISTS {column} TO {to};"
            execute(query, keyspace=keyspace)
            wait(self.validate, DEFAULT_WAIT_TIME)
        except KeyError:
            raise OperationError("Invalid Column Context: %s" % self.context)

    def reverse(self):
        """Returns an Op that reverses the rename operation"""
        column = self.context.get("name")
        table = self.context.get("table")
        keyspace = self.context.get("keyspace")
        to = self.context.get("to")
        return Rename(target="Column", keyspace=keyspace, table=table, column=to, to=column) 


"""
Index

```python
operation = Index(keyspace="Test", table="Person", column="username")
```
"""
class Index(Operation):
    """Creates an Index in C*"""
    DEFAULT, KEYS, VALUES, ENTRIES = 0, 1, 2, 3

    def validate(self) -> bool:
        """Checks whether the index has been created"""
        keyspace = self.context.get("keyspace")
        table = self.context.get("table")
        index = self.context.get("index", self.default)
        metadata = Metadata.fetch(keyspace)
        group = metadata.indexes.get(keyspace, {})
        indexes = group.get(table, {})
        return index in indexes

    @property
    def default(self):
        """Cqlalchemy default name for an index"""
        table = self.context.get("table")
        column = self.context.get("column")
        return "index_{0}_{1}".format(table.lower(), column.lower())

    def execute(self) -> bool:
        """Indexes a column in C*"""
        try:
            keyspace = self.context.get("keyspace")
            table = self.context.get("table")
            column = self.context.get("column")
            category = self.context.get("type", Index.DEFAULT)
            identifier = self.context.get("index", self.default)

            if category == Index.DEFAULT:
                query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}({column});"
            elif category == Index.KEYS:
                query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(KEYS({column}));"
            elif category == Index.VALUES:
                query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(VALUES({column}));"
            elif category == Index.ENTRIES:
                query = f"CREATE INDEX IF NOT EXISTS {identifier} ON {table}(ENTRIES({column}));"
            else: 
                raise OperationError("Please specify a valid Index category")
            execute(query, keyspace=keyspace)
            wait(self.validate, DEFAULT_WAIT_TIME)
        except KeyError:
            raise OperationError("Invalid Column Context: %s" % self.context)

    def reverse(self):
        """Returns an Op that reverses the index operation"""
        keyspace = self.context.get("keyspace")
        index = self.context.get("index", "")
        if index:
            return Drop(target="Index", keyspace=keyspace, index=index, context=self.context) 
        else:
            return Drop(target="Index", keyspace=keyspace, index=self.default, context=self.context)


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

    def validate(self) -> bool:
        """Checks whether the index has been created"""
        keyspace = self.context.get("keyspace")
        target = self.context.get("target")
        metadata = Metadata.fetch(keyspace)
        
        if target == Drop.Keyspace:
            return keyspace in metadata.keyspaces
        elif target == Drop.Table:
            table = self.context.get("table")
            tables = metadata.keyspaces.get(keyspace, {})
            return table in tables
        elif target == Drop.Column:
            table = self.context.get("table")
            column = self.context.get("column")
            tables = metadata.keyspaces.get(keyspace, {})
            table = tables.get(table, {})
            return column in table
        elif target == Drop.Index:
            table = self.context.get("table")
            index = self.context.get("index")
            tables = metadata.indexes.get(keyspace, {})
            table = tables.get(table, {})
            return index in table
        else:
            return False
        
    def execute(self) -> bool:
        """Drops a column in C*"""
        try:
            target = self.context.get("target")
            keyspace = self.context.get("keyspace")

            if target == Drop.Keyspace:
                query = f"DROP KEYSPACE IF EXISTS {keyspace};"
            elif target == Drop.Table:
                keyspace = self.context.get("keyspace")
                table = self.context.get("table")
                query = f"DROP TABLE IF EXISTS {table};"
            elif target == Drop.Column:
                keyspace = self.context.get("keyspace")
                table = self.context.get("table")
                column = self.context.get("column")
                query = f"ALTER TABLE IF EXISTS {table} DROP IF EXISTS {column};"
            elif target == Drop.Index:
                keyspace = self.context.get("keyspace")
                index = self.context.get("index")
                query = f"DROP INDEX IF EXISTS {index};"
            else:
                raise OperationError("Please specify a valid Drop category")

            execute(query, keyspace=keyspace)
            wait(self.validate, DEFAULT_WAIT_TIME)
        except KeyError:
            raise OperationError("Invalid Column Context: %s" % self.context)
        
    def reverse(self):
        """Attempts to reverse the Operation"""
        target = self.context.get("target")
        context = self.context.get("context")
        if not context:
            raise OperationError("We cannot reverse Drop without a context")
        
        if target == Drop.Keyspace:
            return Keyspace(**context)
        elif target == Drop.Table:
            return Table(**context)
        elif target == Drop.Column:
            return Column(**context)
        elif target == Drop.Index:
            return Index(**context)
        else:
            raise OperationError("Cannot reverse Drop Operation on unknown target: %s" % target)


"""
Truncate
Allows you to remove all the rows in a Table

```python
operation = Truncate(keyspace="Test", table="Friends")
```
"""
class Truncate(Operation):
    """Allows you to Truncate a Table"""

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
            wait(self.validate, DEFAULT_WAIT_TIME)
        except KeyError:
            raise OperationError("Invalid Truncate Context: %s" % self.context)
        
    def reverse(self):
        """Attempts to reverse the Operation"""
        raise OperationError("We cannot automatically reverse Truncate Operations.")


"""
Options
Use this Operation to re-configure Keyspaces and Tables

```python
# Modify the replication factor and topology strategy for a Keyspace 

operation = Options(
    target = "Keyspace", keyspace = "Library",
    settings = {
        "replication" : {
            "NetworkTopologyStrategy" : 5
        }
    }
)

# Modify Table settings 

operation = Options(
    target = "Table", table = "Person",
    settings = {
        "comment" : "Stores properties of a people in our model"
    }
)
```
"""
class Options(Operation):
    Keyspace, Table = "Keyspace", "Table"

    def validate(self) -> bool:
        """Checks whether the Table has been truncated"""
        return True 
        
    def execute(self) -> bool:
        """Removes all the data in a Table"""
        try:
            target = self.context.get("target")
            keyspace = self.context.get("keyspace")
            query = None 
            if target == Options.Keyspace:
                settings = self.context.get("settings", {})
                if "replication" not in settings:
                    strategy = {"NetworkTopologyStrategy" : DEFAULT_REPLICAS}
                else:
                    strategy = settings.get("replication")

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
                else:
                    raise OperationError("Invalid Keyspace configuration dictionary: %s" % settings)
                
                query = "ALTER KEYSPACE IF EXISTS {keyspace} WITH replication = {replication}" 
                query = query.format(keyspace=keyspace, replication=replication)
            
            elif target == Options.Table:
                settings_validator = {
                    "caching" : {"keys" : str, "rows_per_partition" : int},
                    "read_repair" : str,
                    "memtable_flush_period_in_ms" : int,
                    "compression" : str,
                    "compaction" : {
                        "class" : str, 
                        "enabled" : bool, 
                        "chunk_length_in_kb" : int, 
                        "crc_check_chance" : float, 
                        "compression_level" : int,
                    }, 
                    "default_time_to_live" : int, 
                    "bloom_filter_fp_chance" : float, 
                    "gc_grace_seconds" : int, 
                    "additional_write_policy" : str, 
                    "cdc" : bool, 
                    "speculative_retry" : str, 
                    "comment" : str, 
                }
                settings = self.context.get("settings")
                table = self.context.get("table")
                configuration = {}
                if settings:
                    for name, item in settings.items():
                        name = name.lower()
                        if name in settings_validator:
                            validator = settings_validator.get(name)
                            value = schema.Schema(validator).validate(item)
                            configuration[name] = value 
                    if configuration:
                        variables = []
                        for name, value in configuration.items():
                            value = repr(value)
                            variables.append(f"{name} = {value}")
                        config_options = " AND".join(variables)
                        config_options = f"WITH {config_options}"
                    query = "ALTER TABLE IF EXISTS {table} {options}"
                    query = query.format(table=table, options=config_options)
                else:
                    raise OperationError("Provide valid coniguration options for Table: %s" % settings)
            else:
                raise OperationError("We can only ALTER Keyspace and Table")
            if not query:
                raise OperationError("Provide options for either Keyspace or Table")
            
            execute(query)
            wait(self.validate, DEFAULT_WAIT_TIME)
        except KeyError:
            raise OperationError("Invalid Truncate Context: %s" % self.context)
        
    def reverse(self):
        """Attempts to reverse the Operation"""
        raise OperationError("We cannot automatically reverse Option operations") 


