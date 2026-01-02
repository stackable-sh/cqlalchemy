"""CQL to Python Bridge"""

import uuid
import threading
import copy
import textwrap
from enum import Enum
from typing import List, Dict, Union, Any

from multidict import MultiDict
from cassandra import ConsistencyLevel
from cassandra.query import SimpleStatement
from cassandra.policies import RetryPolicy

from cqlalchemy.options import debug, verbose, keyspace
from cqlalchemy.core.builtins import Local, Global, IllegalStateException, now
from cqlalchemy.connection.cql import expr


class CqlQueryException(Exception):
    """An Error that signifies that something bad happened during a CqlQuery"""
    pass


class Consistency(object):
    """Context Manager Implementation for controlling Apache Cassandra Consistency Level on a Thread Local basis."""

    def __init__(self, level, variable="consistency"):
        self.level = level
        self.variable = variable
        self.previous = None

    def __enter__(self):
        """Changes the consistency level for the current execution context."""
        local = Local.instance()
        if hasattr(local, self.variable):
            self.previous = getattr(local, self.variable)
        setattr(local, self.variable, self.level)

    def __exit__(self, *arguments, **kwds):
        """Reverts to the previous consistency level after exit"""
        local = Local.instance()
        if self.previous:
            setattr(local, self.variable, self.previous)


"""
Level:
Provides intuitive, and fine grained control for consistency level on a per 
thread/local execution basis.

```python
with Level.Quorum:
    pass # Do some stuff here.
    
with Level.All:
    pass # Do some highly consistent thing here.
```
"""


class Level(object):
    """Manages Different Consistency Levels"""

    Any = Consistency(ConsistencyLevel.ANY)
    All = Consistency(ConsistencyLevel.ALL)
    Quorum = Consistency(ConsistencyLevel.QUORUM)
    One = Consistency(ConsistencyLevel.ONE)
    Two = Consistency(ConsistencyLevel.TWO)
    Three = Consistency(ConsistencyLevel.THREE)
    LocalQuorum = Consistency(ConsistencyLevel.LOCAL_QUORUM)
    EachQuorum = Consistency(ConsistencyLevel.EACH_QUORUM)
    Local = Consistency(ConsistencyLevel.LOCAL_ONE)


class Linearization(object):
    """Linearization Levels for Queries"""
    Serial = Consistency(ConsistencyLevel.SERIAL, variable="serial")
    Local = Consistency(ConsistencyLevel.LOCAL_SERIAL, variable="serial")


class CqlQuery(object):
    """An object that can execute CQL queries on Apache Cassandra and return results"""

    def __init__(self, query, keyspace=None, idempotent=False):
        """Every CqlQuery object requires a string query"""
        self.keyspace = keyspace
        self.query = query
        self.results = None
        self.iterator = None
        self.idempotent = idempotent
        self.executed = False

    def execute(self, **keywords):
        """Executes the query associated with this object"""
        try:
            if not self.query:
                raise CqlQueryException(
                    "Please set the query attribute of CqlQuery before you proceed"
                )
            world = Global.instance()  # Get a hold of the shared global object
            if not world.connected:
                raise RuntimeError("You are not connected to Apache Cassandra")

            thread = Local.instance()
            if not hasattr(thread, "consistency"):
                thread.consistency = ConsistencyLevel.ONE
            if not hasattr(thread, "serial"):
                thread.serial = ConsistencyLevel.SERIAL

            if self.keyspace:
                world.session.set_keyspace(self.keyspace)
            statement = SimpleStatement(
                self.query,
                is_idempotent=self.idempotent,
                consistency_level=thread.consistency,
                serial_consistency_level=thread.serial,
            )
            if debug() and verbose():
                print(self.query)
            self.results = world.session.execute(statement)
            self.executed = True
            return self
        except Exception as e:
            raise e
    
    def text(self):
        """Returns the CQL query as a string"""
        return self.query
    
    def __str__(self):
        """Returns the CQL query as a string"""
        return self.text()

    def __iter__(self):
        """CqlQuery objects yields an ordered dictionary of rows from the datastore"""
        if not self.executed:
            self.execute()
        if self.results is None:
            raise StopIteration("No results from Apache Cassandra")
        else:
            for row in self.results:
                yield row


def execute(query, keyspace=None, idempotent=False):
    """A shortcut for executing one-time statements"""
    query = CqlQuery(query, keyspace=keyspace, idempotent=idempotent)
    query.execute()
    return query.results


"""
AbstractQuery:
An object which uses the builder pattern to allow you to write fluent SELECT queries for C*
which respects Entity objects, and their built in descriptors. 

For example: 

``` python
from cqlalchemy import Model, UUID, String, Integer, Blob, Text
from cqlalchemy import row

class Book(Model):
    isbn = String(key=True, primary=True)
    name = String(index=True, required=True)
    pages = Integer(required=True, index=True)
    cover = Blob(required=False)
    description = Text(length=250, required=True, index=True)

# ... insert some book objects into the datastore 
    
query = Book\
    .objects\
    .where(
        row("name") == "War & Peace",
        row("pages") <= 100,
    )\
    .distinct("name", "isbn")\
    .order_by("isbn", desc=True)\
    .limit(10)\
.execute(filter=True)

# Use the explicit filter flag to ask Apache Cassandra to run this query even if it is expensive. 
book = query.first()
```

Let's model price fluctuations so that we can test GROUP BY, AVG, SUM, MAX, MIN, and COUNT

```python
from datetime import date, timedelta

class Price(Model):
    id = UUID(key=True, primary=True)
    date = Date(key=True, required=True, index=True, default=date.today)
    amount = Float(index=True, required=True)
    book = Reference(Book, required=True)
    currency = String(choices=["USD", "GBP", "CAD",])

amount = 49.99
instant = date.today()

print("Creating new prices for the next ten days")

for i in range(100):
    increase = amount + i
    future = instant + timedelta(days=i)
    Price.create(amount=increase, book=book, currency="USD", date=future)
```

Let's find the most expensive price for our book

``` python
query = Price.objects.max("amount").where(book=book)
query.execute()
print("Amount: %s" % query.get())
```

Let's select a few columns from the Book model instead, and find the lowest price for all our books 

```python
results = Price\
    .objects\
    .columns("id", "book", "date, "currency", min("amount"))\
    .group_by("book")\
.execute(filter=True)

for id, amount, currency, book, date in results:  
    print(f"ID => {id}"
    print(f"Amount => {currency} {amount}")
    print(f"Date => {date}")
    print(f"Book => {book}")
    print("\n")
```

Let's find the average price of our book over time, and print that out to the console

```python
result = Price\
    .objects\
    .avg("amount")\
    .where(book=book)\
.execute(filter=True)

print(result.get()["amount"])
```

We will now attempt to count all the price objects we have stored

```python
result = Price\
    .objects\
    .count()\
.execute(filter=True)

print("Price Objects: %s" % result.get())
```

Finally, let us count all the books that have a cover image set. 

```python
result = Book\
    .objects\
    .count("cover")\
.execute()
print("Price Objects: %s" % result.get())
```

"""


class AbstractSelectQuery(CqlQuery):
    """A CqlQuery object that uses the builder pattern and understands Models"""

    def __init__(self, entity:"Entity"):
        """Initialize your Builder by passing the class the query needs."""
        from cqlalchemy.core.models import CqlProperty, Entity, Key
        from cqlalchemy.core.builtins import fields

        if not issubclass(entity, Entity):
            raise CqlQueryException("You can only use Entity objects with Builder")

        super(AbstractSelectQuery, self).__init__(query=None)
        self.entity = entity
        self.key = Key.create(entity)
        self.iterator = None
        self._columns_ = []
        self._default_fetch_size_ = 1000
        self._properties_ = fields(self.entity, CqlProperty)
        self._attributes_ = {attribute for attribute in self._properties_}
        self._template_ = "SELECT {distinct}{count}{columns} FROM {table} {where}{group}{order}{limit}{filter};"
        self._distinctive_, self._distinct_ = False, ""
        self._countable_, self._count_ = False, ""
        self._limitable_, self._limit_ = False, ""
        self._orderable_, self._order_ = False, dict()
        self._groupable_, self._group_ = False, set()
        self._whereable_, self._where_ = False, MultiDict()
        self._filterable_, self._filter_ = False, ""

    @property
    def properties(self):
        """Returns all the descriptors on the target object"""
        return self._properties_

    def _marshal_(self, data):
        """Marshal results into an Entity if possible"""
        from cqlalchemy.core.differ import commit

        # 1. Return a count
        if data and self._countable_:
            name, count = data.popitem()
            return count
        # 2. Return the unmodified OrderedDict
        elif data and self._columns_:
            return data
        # 3. Marshal into an Entity
        elif data and self._attributes_ == set(data.keys()):
            entity = self.entity()
            for name in self._attributes_:
                descriptor = self._properties_.get(name)
                value = descriptor.deconvert(data[name])
                entity[name] = value
            entity.validate()
            entity.__saved__ = True
            commit(entity)
            return entity
        else:  # 4. Return the unmodified OrderedDict
            return data
            
    def _build_(self):
        """Builds the Query object for execution"""
        if self._distinctive_:
            if self._countable_:
                raise CqlQueryException(
                    "You may not use COUNT and DISTINCT in the same query"
                )
            if self._columns_:
                raise CqlQueryException(
                    "You may not use specific COLUMNS/AGGREGATES and DISTINCT in the same query"
                )
            columns, count, distinct = "", "", self._distinct_
        elif self._countable_:
            if self._distinctive_:
                raise CqlQueryException(
                    "You may not use COUNT and DISTINCT in the same query"
                )
            if self._columns_:
                raise CqlQueryException(
                    "You may not use COUNT and SPECIFIC COLUMNS in the same query"
                )
            columns, count, distinct = "", self._count_, ""
        elif self._columns_:
            if self._countable_:
                raise CqlQueryException(
                    "You may not use COUNT, and SPECIFIC COLUMNS/AGGREGATES in the same query"
                )
            if self._distinctive_:
                raise CqlQueryException(
                    "You may not use SPECIFIC COLUMNS/AGGREGATES and DISTINCT  in the same query"
                )
            columns, count, distinct = ",".join(self._columns_), "", ""
        else:
            columns, count, distinct = "*", "", ""

        query = self._template_.format(
            distinct=distinct,
            count=count,
            columns=columns,
            table=self.entity.table(),
            where=self._build_where_(),
            group=self._build_group_(),
            order=self._build_order_(),
            limit=self._limit_,
            filter=self._filter_,
        )
        self.query = query.strip()
        return self

    def _build_group_(self):
        """Builds the GROUP BY part of the query"""
        pass
        if self._groupable_:
            pattern = " GROUP BY {names}"
            result = pattern.format(",".join(self._group_))
            return result
        else:
            return ""

    def _build_order_(self):
        """Builds the ORDER BY part of the query"""
        result, started = "", False
        if self._orderable_ and self._whereable_:
            for name in self.key.partition:
                if name not in self._where_:
                    raise CqlQueryException(
                        "You must add WHERE clause with the `partition key(s)` to use ORDER BY"
                    )
        if self._orderable_:
            for name in sorted(self._order_.keys()):
                direction = self._order_[name]
                if not started:
                    pattern = " ORDER BY {name} {direction}"
                    result += pattern.format(name=name, direction=direction)
                    started = True
                else:
                    pattern = ", {name} {direction}"
                    result += pattern.format(name=name, direction=direction)
            return result
        else:
            return ""

    def _build_where_(self):
        """Builds the WHERE part of a query, obeying C* idiosyncracies"""
        result, started = "", False
        where = copy.deepcopy(self._where_)
        if self._distinctive_ and self._whereable_:
            properties = self._properties_
            for name in where:
                property = properties.get(name)
                if name in self.key.partition or property.static:
                    continue
                else:
                    raise CqlQueryException(
                        "You can only filter on `partition` keys and `static` columns if you use DISTINCT"
                    )
        if self._whereable_:
            # Process the keys first, and in order (partition keys, then composite, then clustering keys)
            for name in self.key.parts:
                if name in where:
                    part = where.pop(name)
                    if not started:
                        result += "WHERE {part}".format(part=part)
                        started = True
                    else:
                        result += " AND {part}".format(part=part)
            # Process secondary indexes next, and return the build
            for name, value in where.items():
                if not started:
                    result += "WHERE {part}".format(part=value)
                    started = True
                else:
                    result += " AND {part}".format(part=value)
            return result
        else:
            return ""

    def _parse_where_(self, arguments, keywords):
        """An internal helper method for formulating WHERE queries"""
        from cqlalchemy.connection.cql.expr import Operator, EQ, NULL
        
        properties = self._properties_
        disallowed = (NULL,)

        # Process *argument lists first
        for value in arguments:
            if not isinstance(value, Operator):
                raise CqlQueryException("You must provide an Operator for the arguments")
            if isinstance(value, disallowed):
                raise CqlQueryException("You cannot use %s in the arguments in a WHERE clause" % value)
            if not value.left:
                raise CqlQueryException("You must provide a LHS value for the operator")
            if value.right is None:
                raise CqlQueryException("You must provide a RHS value for the operator") 
            value.entity = self.entity
            part = str(value)
            self._where_[value.left] = part
        
        # Process **keyword arguments next to automatically create operators.
        for name, value in keywords.items():
            property = properties.get(name, None)
            if not property:
                raise CqlQueryException(
                    "The %s Property doesn't exist on: %s" % (name, self.entity)
                )
            if (
                (hasattr(property, "key") and property.key)
                or property.indexed()
                or property.static
            ):
                if isinstance(value, Operator):
                    if value.right is None:
                        raise ValueError(
                            "Your Operator must have its RHS set to be valid"
                        )
                    if isinstance(value, disallowed):
                        raise CqlQueryException("You cannot use %s in the arguments in a WHERE clause" % value)
                    operator = value
                    operator.entity = self.entity
                    operator.left = name
                    part = str(operator)
                    self._where_[name] = part
                else:
                    # If the user did not specify an operator, use the EQ operator
                    operator = EQ(right=value)
                    operator.left = name
                    operator.entity = self.entity
                    part = str(operator)
                    self._where_[name] = part
            else:
                raise CqlQueryException(
                    "You can only use WHERE on keys and secondary indexes: %s" % (name)
                )

        if self._where_:
            self._whereable_ = True

    def _allow_filtering_(self):
        """Adds the ALLOW FILTERING clause to the internal query template"""
        if not self._filterable_:
            self._filter_ = " ALLOW FILTERING"
            self._filterable_ = True
        return self

    def order_by(self, name, asc:bool=None, desc:bool=None):
        """Adds the ORDER BY to the Query"""
        if not asc and not desc:
            raise CqlQueryException(
                "You must provide either the asc or desc keyword arguments"
            )
        if asc and desc:
            raise CqlQueryException(
                "You cannot use both ASC and DESC in the same query"
            )
        property = self._properties_.get(name, None)
        if property.key and name in self.key.cluster:
            direction = "ASC" if asc else "DESC"
            self._order_[name] = direction
            self._orderable_ = True
            return self
        else:
            raise CqlQueryException(
                "Property: %s does not exist or is not a clustering key" % name
            )

    def group_by(self, *names):
        """Adds GROUP BY to the Query"""
        # Cassandra only allows you to group by key
        for name in names:
            if name not in self._properties_:
                raise CqlQueryException(
                    "{name} does not exist within {entity}".format(
                        name=name, entity=self.entity.table()
                    )
                )
            descriptor = self._properties_[name]
            if not hasattr(descriptor, "key") or getattr(descriptor, "key", False):
                raise CqlQueryException(
                    "{name} is not a primary or clustering Key".format(name=name)
                )
            if descriptor.key is True:
                self._group_.add(name)
        if self._group_:
            self._groupable_ = True
        return self

    def where(self, *arguments, **keywords):
        """Dynamically builds the WHERE clause from **keywords"""
        self._parse_where_(arguments, keywords)
        return self

    def count(self, name=None):
        """Builds the COUNT(*) section of the internal template"""
        if self._distinctive_:
            raise CqlQueryException(
                "You cannot use the DISTINCT and COUNT clause in the same query"
            )
        if name:
            self._count_ = f"COUNT({name})"
        else:
            self._count_ = "COUNT(*)"
        self._countable_ = True
        return self

    def limit(self, value):
        """LIMIT for the query"""
        self._limit_ = " LIMIT {value}".format(value=value)
        self._limitable_ = True
        return self

    def ttl(self, name, alias=None):
        """TTL for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"No attribute named {name} on {self.entity.__name__}")
        if name in self.key.parts:
            raise CqlQueryException("You cannot use WRITETIME on any primary key")
        part = str(expr.ttl(name, alias))
        self._columns_.append(part)
        return self

    def writetime(self, name, alias=None):
        """WRITETIME for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"No attribute named {name} on {self.entity.__name__}")
        if name in self.key.parts:
            raise CqlQueryException("You cannot use WRITETIME on any primary key")
        part = str(expr.writetime(name, alias))
        self._columns_.append(part)
        return self

    def avg(self, name, alias=None):
        """AVG for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"No attribute named {name} on {self.entity.__name__}")
        part = str(expr.avg(name, alias))
        self._columns_.append(part)
        return self

    def max(self, name, alias=None):
        """MAX for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"No attribute named {name} on {self.entity.__name__}")
        part = str(expr.max(name, alias))
        self._columns_.append(part)
        return self

    def min(self, name, alias=None):
        """MIN for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"No attribute named {name} on {self.entity.__name__}")
        part = str(expr.min(name, alias))
        self._columns_.append(part)
        return self

    def sum(self, name, alias=None):
        """SUM for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"No attribute named {name} on {self.entity.__name__}")
        part = str(expr.sum(name, alias))
        self._columns_.append(part)
        return self

    def columns(self, *names):
        """Allows you to select a specific set of columns from the Table"""
        duplicates = set()
        for name in names:
            if name in duplicates:
                continue
            duplicates.add(name)
            if isinstance(name, str):
                if name not in self._properties_:
                    raise ValueError(
                        f"No attribute named {name} on {self.entity.__name__}"
                    )
                self._columns_.append(name)
            elif isinstance(name, expr.Functor):
                self._columns_.append(name())
            else:
                raise ValueError(
                    f"Parameter {name} must be an instance of str, or a CQL Function"
                )
        return self

    def contains(self, name, value=None, key=None):
        """Filter by indexed values of the default `data` collection for Expando, SortedSet, Array"""
        from cqlalchemy.connection.cql.expr import CONTAINS
        from cqlalchemy.core.commons import Map, Set, List

        if not (value or key):
            raise ValueError("You must provide the `value` or `key` parameter.")
        if name in self.properties:
            property = self.properties[name]
            if not isinstance(property, (Map, Set, List)):
                raise ValueError("Property must be a Map, Set, List, or Tuple")
            if key:
                query = {name : CONTAINS(key, key=True)}
                return self.where(**query)._allow_filtering_()
            else:
                query = {name : CONTAINS(value, key=False)}
                return self.where(**query)._allow_filtering_()
        else:
            raise CqlQueryException(
                "We could not find the customary `data` attribute for Collection objects"
            )

    def distinct(self):
        """Adds the DISTINCT clause to the query"""
        for name, property in self._properties_.items():
            if name in self.key.partition or property.static:
                if not self._distinctive_:
                    part = f"DISTINCT {name}"
                    self._distinct_ = part
                    self._distinctive_ = True
                else:
                    part = ", %s" % name
                    self._distinct_ += part
        return self

    def execute(self, filter=False):
        """Executes the query applying ALLOW FILTERING if required"""
        if filter:
            self._allow_filtering_()
        self._build_()
        return super(AbstractSelectQuery, self).execute()

    def text(self):
        """Returns the CQL query as a string"""
        self._build_()
        return self.query

    def first(self):
        """Returns the first result of the query"""
        stream = list(self)
        if len(stream) >= 1:
            data = stream[0]
            return self._marshal_(data)
        else:
            raise CqlQueryException("No Result Exception")

    def get(self):
        """Returns the first result from the query."""
        try:
            if not self.iterator:
                self.iterator = iter(self)
            data = next(self.iterator)
            return self._marshal_(data)
        except StopIteration:
            return None

    def all(self):
        """Returns a generator with data that has been marshalled into an entity"""
        for data in list(self):
            output = self._marshal_(data)
            yield output

    def one(self):
        """Expects, and returns only one result, any more results will throw a ResultException"""
        first, second = self.get(), self.get()
        if second:
            raise CqlQueryException("Expected only one result, received more than one.")
        return first


class SelectQuery(object):
    """A CqlQuery object for building SELECT queries"""

    def __init__(self, entity:"Entity"):
        """Initialize your Builder by passing the class the query needs."""
        self.query = AbstractSelectQuery(entity)
    
    @property
    def entity(self):
        """Returns the entity the query is built for"""
        return self.query.entity

    @property
    def properties(self):
        """Returns all the descriptors on the target object"""
        return self.query.properties
            
    def order_by(self, name, asc=None, desc=None):
        """Adds the ORDER BY to the Query"""
        self.query.order_by(name, asc, desc)
        return self

    def group_by(self, *names):
        """Adds GROUP BY to the Query"""
        self.query.group_by(*names)
        return self

    def where(self, *arguments, **keywords):
        """Dynamically builds the WHERE clause from **keywords"""
        self.query.where(*arguments, **keywords)
        return self

    def count(self, name=None):
        """Builds the COUNT(*) section of the internal template"""
        self.query.count(name)
        return self

    def limit(self, value):
        """LIMIT for the query"""
        self.query.limit(value)
        return self

    def ttl(self, name, alias=None):
        """TTL for the @name property"""
        self.query.ttl(name, alias)
        return self

    def filter(self):
        """Turn on filtering on the query"""
        self.query._allow_filtering_()
        return self 

    def writetime(self, name, alias=None):
        """WRITETIME for the @name property"""
        self.query.writetime(name, alias)
        return self

    def avg(self, name, alias=None):
        """AVG for the @name property"""
        self.query.avg(name, alias)
        return self
    
    def max(self, name, alias=None):
        """MAX for the @name property"""
        self.query.max(name, alias)
        return self

    def min(self, name, alias=None):
        """MIN for the @name property"""
        self.query.min(name, alias)
        return self

    def sum(self, name, alias=None):
        """SUM for the @name property"""
        self.query.sum(name, alias)
        return self

    def columns(self, *names):
        """Allows you to select a specific set of columns from the Table"""
        self.query.columns(*names)
        return self

    def contains(self, name, value=None, key=None):
        """Filter by indexed values of the default `data` collection for Expando, SortedSet, Array"""
        self.query.contains(name, value, key)
        return self
    
    def distinct(self):
        """Adds the DISTINCT clause to the Query"""
        self.query.distinct()
        return self

    def execute(self, filter=False):
        """Executes the query applying ALLOW FILTERING if required"""
        return self.query.execute(filter)

    def text(self):
        """Returns the CQL query as a string"""
        return self.query.text()

    def first(self):
        """Returns the first result of the query"""
        return self.query.first()

    def get(self):
        """Returns the first result from the query."""
        return self.query.get()

    def all(self):
        """Returns a generator with data that has been marshalled into an entity"""
        return self.query.all()

    def one(self):
        """Expects, and returns only one result, any more results will throw a ResultException"""
        return self.query.one()
    
    def __str__(self):
        return self.query.text()


"""
select:
Fluent entry point for building SELECT queries from Models
"""
def select(entity: "Entity"):
    """Builds a SELECT query"""
    return SelectQuery(entity)


"""

```python
Author = Table("Author", Expando)
instance = Author.create(name="Sam Harris", age=49, category="Philosophy")
id = instance["id"] 

author = Author.read(id)
assert author["name"] == "Sam Harris"
assert author["age"] == 49
assert author["category"] == "Philosophy"

author["name"] = "Shakespeare"
author["address"] = "#10 Downing Street, London"
author["age"] = 53
author["publisher"] = "Barnes & Noble, Inc"
author.save()                                                                       

authors = Author.objects.all()                                                      # Retrieve all Author entities from C*
results = Author\
    .objects\
    .contains(key="name")\                                            # Find all Authors who have the `name` key
.execute()

results = Author\
    .objects\
    .contains(value="Sun Tzu")\                                                      # Find all Authors who have the `value` value
.execute()     
```

"""


class CollectionQuery(SelectQuery):
    
    def contains(self, name:str="data", value=None, key=None):
        """Filter by indexed values of the default `data` collection for Expando, SortedSet, Array"""
        return super().contains(name, value, key)



class InsertQuery(CqlQuery):
    """InsertQuery: Fluent entry point for building INSERT queries from Models"""
    def __init__(self, entity: "Entity"):
        super().__init__(entity)
    
    def values(self, **context):
        """Set values for the INSERT query"""
        pass
    
    def execute(self):
        """Execute the INSERT query"""
        pass 

class UpdateQuery(CqlQuery):
    """UpdateQuery: Fluent entry point for building UPDATE queries from Models"""

    def __init__(self, entity: "Entity"):
        super().__init__(entity)

    def set(self, **context):
        """Set values for the UPDATE query"""
        pass

    def incr(self, value:int=1):
        """Increment the value of a counter column"""
        pass

    def decr(self, value:int=1):
        """Decrement the value of a counter column"""
        pass
    
    def where(self, **context):
        """Add a WHERE clause to the UPDATE query"""
        pass 

    def execute(self):
        """Execute the UPDATE query"""
        return super().execute()


class DeleteQuery(CqlQuery):
    """DeleteQuery: Fluent entry point for building DELETE queries from Models"""
    def __init__(self, entity: "Entity"):
        super().__init__(entity)

    def where(self, **context):
        """Add a WHERE clause to the DELETE query"""
        pass

    def execute(self):
        """Execute the DELETE query"""
        return super().execute()

"""
Batch:

Allows you to execute many related C* operations in one network request. 
We provide support for LOGGED, UNLOGGED, and COUNTER Batch objects through the BatchType Enum. 

```python
from cqlalchemy import Model, Batch, String, BatchType

class Book(Model, version=True):
    name = String(index=True, required=True)
    author = String(index=True, required=True) 

with Batch(): 
    Book.create(name="The Great Gatsby", author="F. Scott Fitzgerald")
    Book.create(name="The Adventures of Huckleberry Finn", author="Mark Twain")
    Book.create(name="To Kill a Mockingbird", author="Harper Lee")

# Use BatchType.Counter & BatchType.Unlogged for COUNTER, and UNLOGGED Batch queries. 
Analytics = Counter("Analytics", ["books",])
stats = Analytics.create()

with Batch(BatchType.Counter):
    stats.incr("books", 3)
```
"""
BatchType = Enum("BatchType", ["Normal", "Unlogged", "Counter"])


class Batch(threading.local):
    """Execute multiple queries in a single network request to get per partition isolation."""

    batches = set()

    def __init__(self, type: BatchType = BatchType.Normal, **context):
        """Initializes a Batch object which you can execute"""
        self.type = type
        self.keyspace = context.get("keyspace", keyspace())
        self.context = context
        self.open = False
        self.guid = str(uuid.uuid4())
        self.queries = []
        self.results = None
        self.error = False
        self.exception = None
        self.shared = False
        self.callbacks = []
        self.errbacks = []
        self.run = False
        self.thread = threading.get_native_id()

    @classmethod
    def get(self):
        """Returns the current batch for this thread or None"""
        thread = Local.instance()
        batch = getattr(thread, "batch", None)
        return batch

    @classmethod
    def create(self, type: BatchType=BatchType.Normal, keyspace=None):
        """Creates a new Batch object for the current thread, throws exception if one is currently open"""
        previous = self.get()
        if previous and previous.open:
            raise IllegalStateException("Another Batch is available and active")

        batch = Batch(type, keyspace=keyspace)
        self.batches.add(batch)
        return batch

    def set(self):
        """Internal method to set this batch as the batch for the current thread."""
        if self.get():
            raise IllegalStateException("You cannot have two active Batch objects")
        self.open = True
        thread = Local.instance()
        thread.batch = self

    def unset(self):
        """Internal helper to remove this batch from use"""
        batch = self.get()
        if batch != self:
            raise IllegalStateException(
                "You cannot remove the Batch object for another context"
            )
        self.open = False
        thread = Local.instance()
        thread.batch = None

    def add(self, query):
        """Add new queries to the Batch object"""
        if not query:
            raise ValueError("You must provide a valid query")
        self.queries.append(query)

    def after(self, callbacks):
        """Add callback hooks after the `successful` execution of this batch"""
        if callbacks and isinstance(callbacks, list):
            self.callbacks.extend(callbacks)

    def failure(self, errbacks):
        if errbacks and isinstance(errbacks, list):
            self.errbacks.extend(errbacks)

    def conditional(self):
        """Returns True if this Batch has conditional statements"""
        condition = False
        for query in self.queries:
            if "IF" in query:
                condition = True
                break
        return condition

    def execute(self):
        """Execute this batch and close it"""
        #########################################################################################################
        # 1. By default, when a batch statement returns without an error, you can assume that it has succeeded. #
        #########################################################################################################
        applied = True
        try:
            self.set()
            if not self.queries:
                raise CqlQueryException("Batch Empty: No Queries to Execute")

            query = """BEGIN{type}BATCH\n{queries}\nAPPLY BATCH;"""
            queries = "\n".join(self.queries)
            queries = textwrap.indent(queries, " " * 4)
            type = " "
            if self.type in (BatchType.Counter, BatchType.Unlogged):
                type = " %s " % self.type.name.upper()
            query = query.format(type=type, queries=queries)
            if not self.open:
                raise IllegalStateException(
                    f"Batch: {self.guid} must be open and ready for use before you can `execute`"
                )

            ###################################################################################
            # 2. Except in the case where Batch statements have conditional updates/deletes,  #
            # in this case you have to explicitly check whether the batch succeeded.          #
            ###################################################################################
            self.results = execute(query, keyspace=self.keyspace)
            if self.results is not None:
                row = self.results.current_rows[0] if self.results.current_rows else []
                if row:
                    applied = row["[applied]"]
            self.open = False
            self.run = True
        except Exception as e:
            self.exception = e
            self.error = True
            self.open = False
            applied = False
            # If the execution of the batch failed, run the errbacks regardless.
            if not self.run:
                for function in self.errbacks:
                    function(batch=self)
            raise e
        finally:
            self.unset()
        # Fire call backs after the batch succeeded
        if applied:
            for function in self.callbacks:
                function()

    def __enter__(self):
        """Changes the current Thread Local Consistency Level"""
        batch = self.get()
        if batch and batch != self:
            raise IllegalStateException(
                "You cannot have more than one active Batch object at once"
            )
        self.set()
        return self

    def __exit__(self, *arguments, **kwds):
        """Execute the Batch upon exit"""
        self.unset()
        if not self.run and not self.shared:
            self.execute()


class Group(Batch):
    def __init__(self, **context):
        """Not a Batch, but executes a group of (usually) idempotent queries sequentially"""
        self.keyspace = context.get("keyspace", keyspace())
        self.idempotent = context.get("idempotent", True)
        self.context = context
        self.open = False
        self.guid = str(uuid.uuid4())
        self.queries = []
        self.results = None
        self.error = False
        self.exception = None
        self.shared = False
        self.callbacks = []
        self.errbacks = []
        self.run = False
        self.thread = threading.get_native_id()

    def execute(self):
        """Execute every query sequentially"""
        applied = True
        try:
            self.set()
            if not self.open:
                raise IllegalStateException(
                    f"Group: {self.guid} must be open and ready for use before you can `execute`"
                )
            self.results = []
            if not self.queries:
                raise CqlQueryException("Group Empty: No Queries to Execute")
            for query in self.queries:
                result = execute(
                    query, keyspace=self.keyspace, idempotent=self.idempotent
                )
                self.results.append(result)
            self.open = False
            self.run = True
            applied = True
        except Exception as e:
            self.exception = e
            self.error = True
            self.open = False
            applied = False
            # If the execution of one of the queries in a group failed, run the errbacks regardless.
            if not self.run:
                for function in self.errbacks:
                    function(batch=self)
            raise e
        finally:
            self.unset()
        # Fire call backs after the batch succeeded
        if applied:
            for function in self.callbacks:
                function()
        

