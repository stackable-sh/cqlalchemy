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

"""CQL to Python Bridge"""


import threading
import textwrap
import traceback
from enum import Enum
from threading import RLock
from weakref import WeakValueDictionary, WeakSet
from collections import OrderedDict
from typing import List, Dict, Union, Any, Callable, Generator, Optional, Type, Set
from contextlib import contextmanager as manager

import uuid_utils.compat as uuid
from multidict import MultiDict
from cassandra import ConsistencyLevel
from cassandra.query import SimpleStatement

from cqlalchemy.core.signals import subscribe, Event, propagate
from cqlalchemy.exceptions import BaseException
from cqlalchemy.options import debug, verbose, keyspace
from cqlalchemy.core.builtins import Local, Global
from cqlalchemy.connection.cql.expr import Variable, Transaction, Condition
from cqlalchemy.connection.cql import expr
from cqlalchemy.exceptions import (
    CqlQueryException,
    IllegalStateException,
    IsolatedStaticFieldException,
)


class AtomException(BaseException):
    """Raised when a transaction fails"""
    results : Any = None
    atom : "Atom" = None

    def __init__(self, atom: "Atom", results: Any = None, message: str = "Accord Transaction was not applied successfully"):
        super().__init__(message)
        self.results = results
        self.atom = atom


class BatchException(BaseException):
    """Raised when a batch transaction fails"""
    results : Any = None
    batch : "Batch" = None

    def __init__(self, batch: "Batch", results: Any = None, message: str = "Batch was not applied successfully"):
        super().__init__(message)
        self.results = results
        self.batch = batch


class Consistency(object):
    """Manages Consistency Level on a Thread Local basis."""

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


class AbstractReadQuery(CqlQuery):
    """A CqlQuery object that uses the builder pattern and understands Models"""

    def __init__(self, entity:"Entity"):
        """Initialize your Builder by passing the class the query needs."""
        from cqlalchemy.core.models import CqlProperty, Entity, Key
        from cqlalchemy.core.builtins import fields

        if not issubclass(entity, Entity):
            raise CqlQueryException("You can only use Entity objects with Builder")

        super(AbstractReadQuery, self).__init__(query=None)
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
        self._whereable_, self._where_ = False, None
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
                value = descriptor.deconvert(entity, data[name])
                if descriptor.required and value is None:
                    continue
                else:   
                    entity[name] = value
            entity.validate()
            entity.__saved__ = True
            commit(entity)
            return entity
        else:  # 4. Return the unmodified OrderedDict
            return data
            
    def build(self):
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
                    "You may not use COUNT, and specific COLUMNS or AGGREGATES in the same query"
                )
            if self._distinctive_:
                raise CqlQueryException(
                    "You may not use SPECIFIC COLUMNS/AGGREGATES and DISTINCT in the same query"
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
        return self.query 

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
                if name not in self._where_.columns():
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
        if self._whereable_ and self._where_:
            if self._distinctive_: # CQL idiosyncratic check. 
                for name in self._where_.columns():
                    property = self.properties.get(name)
                    if name in self.key.partition or property.static:
                        continue
                    else:
                        raise CqlQueryException(
                            "You can only filter on `partition` keys and `static` columns if you use DISTINCT"
                        )
            return str(self._where_)
        else:
            return ""

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
        from cqlalchemy.connection.cql.expr import Where
        if self._where_ is not None:
            self._where_.add(*arguments, **keywords)
        else:
            self._where_ = Where(self.entity())
            self._where_.add(*arguments, **keywords)
            self._whereable_ = True
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
        if not self.query:
            self.build()
        return super(AbstractReadQuery, self).execute()

    def text(self):
        """Returns the CQL query as a string"""
        return self.build()

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
    session: "Session"

    def __init__(self, entity:"Entity", session:Optional["Session"]=None):
        """Initialize your Builder by passing the class the query needs."""
        self.query = AbstractReadQuery(entity)
        self.session = session

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
    
    def filter_by(self, *arguments, **keywords):
        """Dynamically builds the WHERE clause from **keywords and turns on filtering"""
        self.query.where(*arguments, **keywords)
        self.query._allow_filtering_()
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

    def build(self):
        """Build the query and return its text"""
        return self.query.build()

    def first(self):
        """Returns the first result of the query"""
        result = self.query.first()
        return self.cache(result)
    
    def cache(self, entity:"Entity"):
        from cqlalchemy.core.models import Entity
        if entity and isinstance(entity, Entity) and self.session:
            self.session.bind(entity)
        return entity

    def get(self):
        """Returns the first result from the query."""
        result = self.query.get()
        return self.cache(result)

    def all(self):
        """Returns a generator with data that has been marshalled into an entity"""
        for entity in self.query.all():
            yield self.cache(entity)

    def one(self):
        """Expects, and returns only one result, any more results will throw a ResultException"""
        return self.cache(self.query.one())
    
    def __str__(self):
        return self.query.text()


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


class AbstractChangeQuery(object):
    """Base Query Builder for INSERT, UPDATE, and DELETE statements"""

    def __init__(self, entity: "Entity"):
        from cqlalchemy.core.models import CqlProperty, Entity, options
        from cqlalchemy.core.builtins import fields

        if not issubclass(entity, Entity):
            raise TypeError("Entity must be a subclass of Entity")
        if options(entity, "version"):
            raise CqlQueryException("Versioning is not supported for INSERT, UPDATE, and DELETE fluent queries")
            
        self._entity_ = entity
        self._expire_ = entity.__options__.get("expire", 0)
        self._accord_ = entity.__options__.get("accord", False)
        self._batch_ = entity.__options__.get("batch", False)
        self._keyspace_ = entity.__options__.get("keyspace", None)
        self._table_ = entity.table()
        self._properties_ = fields(entity, CqlProperty)

    @property
    def entity(self):
        """Returns the entity the query is built for"""
        return self._entity_

    @property
    def properties(self):
        """Returns all the descriptors on the target object"""
        return self._properties_
    
    def text(self) -> str:
        """Returns the CQL query as a string"""
        return self.build()
    
    def validate(self):
        """Check whether the query is valid on a best-effort basis"""
        pass 

    def build(self) -> str:
        """Builds the CQL query"""
        raise NotImplementedError("Subclasses must implement the build method")

    def execute(self):
        """Execute the INSERT query, respecting transaction and batch options"""
        try:
            query = self.build()
            atom, batch, group = Atom.get(), Batch.get(), Group.get()
            if atom and not self._accord_:
                raise IllegalStateException(f"Entity: {self._entity_} does not support transactions")
            if batch and not self._batch_:
                raise IllegalStateException(f"Entity: {self._entity_} does not support batches")
            if atom and batch:
                raise IllegalStateException("You cannot combine transactions and batches")
            # If we support Accord, then try to join an open transaction if it exists. 
            if atom and atom.open:
                if self._accord_:
                    atom.add(query)
                    return
                else:
                    raise CqlQueryException(f"Entity: {self._entity_} does not support transactions")
            # If we support Batches, then try to join an open batch if it exists.
            if batch and batch.open:
                if self._batch_:
                    batch.add(query)
                    return
                else:
                    raise CqlQueryException(f"Entity: {self._entity_} does not support batches")
            # If not, try and and see if there is an open group on this thread, join it.
            if group and group.open:
                group.add(query)
                return
            # Otherwise, execute the query directly
            execute(query, keyspace=self._keyspace_)
        except Exception as e:
            raise e


class InsertQuery(AbstractChangeQuery):
    """InsertQuery: Fluent entry point for building INSERT queries from Models"""

    def __init__(self, entity: "Entity"):
        super().__init__(entity)
        self._unique_ = ""
        self._ttl_ = ""
        self._values_ = OrderedDict()
        self._template_ = "INSERT INTO {table} ({columns}) VALUES ({values}) {unique}{ttl};"

    def unique(self):
        """Set the unique constraint for the INSERT query"""
        self._unique_ = " IF NOT EXISTS"
        return self

    def validate(self):
        """Validate the INSERT query"""
        if not self._values_:
            raise ValueError("Provide at least one value for the INSERT query")
        return self

    def ttl(self, value:int):
        """Set the TTL for the INSERT query"""
        self._ttl_ = " USING TTL {expire}".format(expire=value) if value else ""
        return self
    
    def values(self, **context):
        """Set values for the INSERT query"""
        for name, property in self._properties_.items():
            if not property.saveable():
                continue 
            else:
                if name in context:
                    value = property.convert(self._entity_(), context[name])
                    self._values_[name] = value
        return self
    
    def build(self) -> str:
        """Builds the CQL query"""
        if not self._values_:
            raise ValueError("Values must be set for an INSERT query to be valid")
        self.validate()
        if not self._ttl_ and self._expire_:
            self.ttl(self._expire_)
        columns, values = [], []
        for name, value in self._values_.items():
            columns.append(name)
            values.append(value)
        return self._template_.format(
            table=self._table_,
            columns=", ".join(columns),
            values=", ".join(values),
            unique=self._unique_,
            ttl=self._ttl_
        )


class DeleteQuery(AbstractChangeQuery):
    """DeleteQuery: Fluent entry point for building DELETE queries from Models"""

    def __init__(self, entity: "Entity"):
        super().__init__(entity)
        self._exists_ = None
        self._predicate_ = None 
        self._columns_ = set()
        self._targets_ = set()
        self._where_ = None
        self._template_ = "DELETE {columns} FROM {table} {where}{conditions};"

    def columns(self, *columns):
        """Set the columns to delete from matching rows"""
        for name in columns:
            if name not in self.properties:
                raise ValueError(f"Property: {name} not found in {self.entity}")
            self._columns_.add(name)
            self._targets_.add(name)
        return self
    
    def remove(self, column:str, index:int=None, key:Any=None):
        """Remove specific columns from matching rows"""
        from cqlalchemy.core.commons import List, Map, Set
        if key is not None and index is not None:
            raise ValueError("You cannot provide both an index and a key for specific column deletes")
        property = self.properties.get(column, None)
        if not property:
            raise ValueError(f"Column: {column} not found in this {self.entity}")
        if isinstance(index, int) and index >= 0:
            if not isinstance(property, List):
                raise TypeError(f"Column: {column} is not a List, cannot delete `index`: {index}`")
            self._columns_.add(f"{column}[{index}]")
            return self 
        if key is not None:
            if isinstance(property, Set):
                raise TypeError(f"Column: {column} is an Unordered Set, \
                    so you cannot delete a specific element by index or key,\
                    use an update() with remove() instead or delete the entire column"
                )
            if not isinstance(property, Map):
                raise TypeError(f"Column: {column} is not a Map, cannot delete `key`: {key}`")
            property = property.converter[0]
            key = property.convert(self.entity(), key)
            self._columns_.add(f"{column}[{key}]")
            self._targets_.add(column)
            return self

    def where(self, *arguments, **keywords):
        """Add a WHERE clause to the DELETE query"""
        from cqlalchemy.connection.cql.expr import Where
        if self._where_:
            self._where_.add(*arguments, **keywords)
        else:
            self._where_ = Where(self.entity())
            self._where_.add(*arguments, **keywords)
            self._where_.keys_only = True
        return self
    
    def when(self, *arguments, **keywords):
        """Add a IF clause to the DELETE query"""
        from cqlalchemy.connection.functions import when as predicate
        if self._predicate_:
            self._predicate_.add(*arguments, **keywords)
        else:
            entity = self.entity()
            self._predicate_ = predicate(*arguments, **keywords)
            self._predicate_.entity = entity 
        return self 
    
    def exists(self):
        """Set the IF EXISTS constraint for the INSERT query"""
        self._exists_ = " IF EXISTS"
        return self
    
    def validate(self):
        qualified = []
        for name in self._targets_:
            descriptor = self.properties.get(name)
            if descriptor.key or descriptor.primary:
                continue
            else:
                qualified.append(name)

        if len(qualified) == 1:
            first = qualified[0]
            descriptor = self.properties.get(first)
            if descriptor.static:
                raise IsolatedStaticFieldException(
                    f"Cannot delete static field `{first}` in isolation"
                )
                
    def build(self):
        """Build the DELETE query"""
        if self._exists_ and self._predicate_:
            raise CqlQueryException("You cannot use IF EXISTS and IF conditions at the same time")
    
        if self._exists_:
            conditions = self._exists_
        elif self._predicate_:
            conditions = str(self._predicate_)
        else:
            conditions = ""
        self.validate()
        return self._template_.format(
            table=self._table_,
            columns=", ".join(self._columns_),
            where=str(self._where_),
            conditions=conditions
        )


class UpdateQuery(AbstractChangeQuery):
    """UpdateQuery: Fluent entry point for building UPDATE queries from Models"""

    def __init__(self, entity: "Entity"):
        super().__init__(entity)
        self._exists_ = ""
        self._predicate_ = None 
        self._values_ = MultiDict()
        self._targets_ = set()
        self._where_ = None
        self._ttl_ = ""
        self._template_ = """UPDATE {table} {ttl}\n    SET {values}\n{where}{conditions};"""

    def append(self, **keywords):
        """Append values to a list column"""
        from cqlalchemy.core.commons import List
        for name, value in keywords.items():
            if name not in self.properties:
                raise ValueError(f"Property: {name} not found in {self.entity}")
            property = self.properties.get(name, None)
            if not isinstance(property, List):
                raise TypeError(f"Property: {name} is not a List, cannot append `value`: {value}`")
            if not isinstance(value, list):
                value = [value,]
            value = property.convert(self.entity(), value)
            expr = "{name} = {name} + {value}".format(name=name, value=value)
            self._values_[name] = expr
            self._targets_.add(name)
        return self
    
    def prepend(self, **keywords):
        """Prepend values to a list column"""
        from cqlalchemy.core.commons import List
        for name, value in keywords.items():
            if name not in self.properties:
                raise ValueError(f"Property: {name} not found in {self.entity}")
            property = self.properties.get(name, None)
            if not isinstance(property, List):
                raise TypeError(f"Property: {name} is not a List, cannot prepend `value`: {value}`")
            if not isinstance(value, list):
                value = [value,]
            value = property.convert(self.entity(), value)
            expr = "{name} = {value} + {name}".format(name=name, value=value)
            self._values_[name] = expr
            self._targets_.add(name)
        return self
    
    def insert(self, column:str, value:Any, index:int):
        """Insert values into a list column"""
        from cqlalchemy.core.commons import List
        if column not in self.properties:
            raise ValueError(f"Property: {column} not found in {self.entity}")
        property = self.properties.get(column, None)
        if not isinstance(property, List):
            raise TypeError(f"Property: {column} is not a List, cannot insert `value`: {value}`")

        T = property.converter
        value = T.convert(self.entity(), value)
        expr = "{column}[{index}] = {value}".format(column=column, index=index, value=value)
        self._values_[column] = expr
        self._targets_.add(column)
        return self
    
    def set(self, **keywords):
        """Set values for the UPDATE query"""
        for name, value in keywords.items():
            if name not in self.properties:
                raise ValueError(f"Property: {name} not found in {self.entity}")
            property = self.properties.get(name, None)
            value = property.convert(self.entity(), value)
            expr = "{name} = {value}".format(name=name, value=value)
            self._values_[name] = expr
            self._targets_.add(name)
        return self

    def ttl(self, value:int):
        """Set the TTL for the INSERT query"""
        atom = Atom.get()
        if atom:
            if not self._accord_:
                raise IllegalStateException(f"Entity: {self._entity_} does not support atomic query dynamics")
            raise CqlQueryException("You cannot set TTL for UPDATES inside transactions.")
        self._ttl_ = " USING TTL {expire}".format(expire=value) if value else ""
        return self

    def add(self, **keywords):
        """Add values to a map or set column"""
        from cqlalchemy.core.commons import Map, Set
        for name, value in keywords.items():
            if name not in self.properties:
                raise ValueError(f"Property: {name} not found in {self.entity}")
            property = self.properties.get(name, None)
            if not isinstance(property, (Map, Set)):
                raise TypeError(f"Property: {name} is not a Map or Set, cannot add `value`: {value}`")
            if isinstance(property, Set):
                if not isinstance(value, (set,)):
                    value = {value,}
            else:
                if not isinstance(value, dict):
                    raise TypeError(f"Value: {value} is not a dict, please provide a dict of key-value pairs")
            value = property.convert(self.entity(), value)
            expr = "{name} = {name} + {value}".format(name=name, value=value)
            self._values_[name] = expr
            self._targets_.add(name)
        return self
    
    def remove(self, **keywords):
        """Remove values from a map or set column"""
        from cqlalchemy.core.commons import Map, Set
        for name, value in keywords.items():
            if name not in self.properties:
                raise ValueError(f"Property: {name} not found in {self.entity}")
            property = self.properties.get(name, None)
            if not isinstance(property, (Map, Set)):
                raise TypeError(f"Property: {name} is not a Map or Set, cannot remove `value`: {value}`")
            if isinstance(property, Map):
                T = property.converter[0]
                property = Set(T.__class__)
            if not isinstance(value, (set,)): 
                if isinstance(value, list):
                    value = set(value)
                else:
                    value = {value,}
            value = property.convert(self.entity(), value)
            expr = "{name} = {name} - {value}".format(name=name, value=value)
            self._values_[name] = expr
            self._targets_.add(name)
        return self
    
    def incr(self, **keywords):
        """Increment the value of a counter or int column"""
        from cqlalchemy.core.commons import Integer, Long, Counter
        for name, value in keywords.items():
            if name not in self.properties:
                raise ValueError(f"Property: {name} not found in {self.entity}")
            property = self.properties.get(name, None)
            if not isinstance(property, (Counter, Integer, Long)):
                raise TypeError(f"Property: {name} is not a Integer, Long or Counter, cannot increment `value`: {value}`")
            value = property.convert(self.entity(), value)
            if isinstance(property, Counter):
                expr = "{name} = {name} + {value}".format(name=name, value=value)
            else:
                atom = Atom.get()
                if atom:
                    if not self._accord_:
                        raise IllegalStateException(f"Entity: {self._entity_} does not support atomic query dynamics")
                    expr = "{name} += {value}".format(name=name, value=value)
                else:
                    raise CqlQueryException("incr()/decr() do not work on non-atomic contexts for {self.entity()}")
            self._values_[name] = expr
            self._targets_.add(name)
        return self

    def decr(self, **keywords):
        """Decrement the value of a counter or int column"""
        from cqlalchemy.core.commons import Integer, Long, Counter
        for name, value in keywords.items():
            if name not in self.properties:
                raise ValueError(f"Property: {name} not found in {self.entity}")
            property = self.properties.get(name, None)
            if not isinstance(property, (Integer, Long, Counter)):
                raise TypeError(f"Property: {name} is not a Integer, Long or Counter, cannot decrement `value`: {value}`")
            value = property.convert(self.entity(), value)
            if isinstance(property, Counter):
                expr = "{name} = {name} - {value}".format(name=name, value=value)
            else:
                atom = Atom.get()
                if atom:
                    if not self._accord_:
                        raise IllegalStateException(f"Entity: {self._entity_} does not support atomic query dynamics")
                    expr = "{name} -= {value}".format(name=name, value=value)
                else:
                    raise CqlQueryException("incr()/decr() do not work on non-atomic contexts for {self.entity()}")
            self._values_[name] = expr
            self._targets_.add(name)
        return self
    
    def where(self, *arguments, **keywords):
        """Add a WHERE clause to the DELETE query"""
        from cqlalchemy.connection.cql.expr import Where
        if self._where_:
            self._where_.add(*arguments, **keywords)
        else:
            self._where_ = Where(self.entity())
            self._where_.add(*arguments, **keywords)
            self._where_.keys_only = True
        return self
    
    def when(self, *arguments, **keywords):
        """Add a IF clause to the DELETE query"""
        from cqlalchemy.connection.functions import when as predicate
        if self._predicate_:
            self._predicate_.add(*arguments, **keywords)
        else:
            entity = self.entity()
            self._predicate_ = predicate(*arguments, **keywords)
            self._predicate_.entity = entity 
        return self 
    
    def exists(self):
        """Set the IF EXISTS constraint for the UPDATE or DELETE query"""
        self._exists_ = " IF EXISTS"
        return self
    
    def validate(self):
        qualified = []
        for name in self._targets_:
            descriptor = self.properties.get(name)
            if descriptor.key or descriptor.primary:
                continue
            else:
                qualified.append(name)

        if len(qualified) == 1:
            first = qualified[0]
            descriptor = self.properties.get(first)
            if descriptor.static:
                raise IsolatedStaticFieldException(
                    f"Cannot update static field `{first}` in isolation"
                )
                
    def build(self):
        """Build the DELETE query"""
        if self._exists_ and self._predicate_:
            raise ValueError("You cannot use IF EXISTS and IF conditions at the same time")
        if self._exists_:
            conditions = self._exists_
        elif self._predicate_:
            conditions = str(self._predicate_)
        else:
            conditions = ""
        assignments = []
        for name, value in self._values_.items():
            assignments.append(value.strip())
        if not assignments:
            raise ValueError("Provide at least one value for the UPDATE query")
        if not self._where_:
            raise ValueError("Provide at least one WHERE condition for the UPDATE query")
        
        self.validate()
        assignments = ", ".join(assignments)

        return self._template_.format(
            table=self._table_,
            ttl=self._ttl_,
            values=assignments,
            where=str(self._where_),
            conditions=conditions
        )


"""
Batch:

Allows you to execute many C* operations in one network request. 
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
    batches : Set["Batch"] = WeakSet()
    objects : Set[Union["Pointer", "Entity"]] 

    def __init__(self, type: BatchType = BatchType.Normal, **context):
        """Initializes a Batch object which you can execute"""
        self.type = type
        self.keyspace = context.get("keyspace", keyspace())
        self.context = context
        self.open = False
        self.guid = str(uuid.uuid7())
        self.queries = []
        self.results = None
        self.error = False
        self.exception = None
        self.shared = False
        self.callbacks = []
        self.errbacks = []
        self.run = False
        self.applied = False 
        self.objects = WeakSet()
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

    def include(self, object: Union["Pointer", "Entity"]):
        """Include an object (Pointer or Entity) as a participant in the batch"""
        self.objects.add(object)

    def set(self):
        """Internal method to set this batch as the batch for the current thread."""
        previous = self.get()
        if previous and previous != self:
            raise IllegalStateException("You cannot have two active Batch objects")
        thread = Local.instance()
        if hasattr(thread, "atom") and thread.atom:
            raise IllegalStateException("You cannot combine transactions and batches")
        self.open = True
        thread.batch = self

    def unset(self):
        """Internal helper to remove this batch from use"""
        batch = self.get()
        if batch and batch != self:
            raise IllegalStateException(
                "You cannot remove the Batch object for another context"
            )
        elif batch and batch == self:
            self.open = False
            thread = Local.instance()
            thread.batch = None
        else:
            pass 

    def add(self, query):
        """Add new queries to the Batch object"""
        if not query:
            raise ValueError("You must provide a valid query not: %s" % query)
        text = query if isinstance(query, str) else query.text()
        valid = ['INSERT', 'UPDATE', 'DELETE']
        query_type = text.strip().split(" ")[0].upper()
        if query_type not in valid:
            raise CqlQueryException("You must provide a valid INSERT, UPDATE, or DELETE query not %s" % query_type)
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
        self.applied = True
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
                    self.applied = row["[applied]"]
            self.open = False
            self.run = True

            if self.conditional() and not self.applied:
                raise BatchException(self, results=self.results, message="Batch was not applied successfully")
        except Exception as e:
            self.exception = e
            self.error = True
            self.open = False
            self.applied = False
            # If the execution of the batch failed, run the errbacks regardless.
            if not self.run:
                for function in self.errbacks:
                    function(batch=self)
            raise e
        finally:
            self.unset()
        
        try:
            # Fire call backs after the batch succeeded
            if self.applied:
                for function in self.callbacks:
                    function()
            propagate(Event.UOW_END, sender=self, batch=self)
        except Exception as e:
            traceback.print_exc(e)

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
        try:
            if not self.run and not self.shared:
                self.execute()
        except Exception as e:
            raise e
        finally:
            self.unset()


class Group(Batch):
    """Not a Batch, but executes a group of (usually) idempotent queries sequentially"""
    
    def __init__(self, **context):
        """Initializes a Group object which you can execute"""
        self.keyspace = context.get("keyspace", keyspace())
        self.idempotent = context.get("idempotent", True)
        self.context = context
        self.open = False
        self.guid = str(uuid.uuid7())
        self.queries = []
        self.results = None
        self.error = False
        self.exception = None
        self.shared = False
        self.callbacks = []
        self.errbacks = []
        self.run = False
        self.applied = False
        self.objects = WeakSet()
        self.thread = threading.get_native_id()

    def execute(self):
        """Execute every query sequentially"""
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
            self.applied = True
        except Exception as e:
            self.exception = e
            self.error = True
            self.open = False
            self.applied = False
            # If the execution of one of the queries in a group failed, run the errbacks regardless.
            if not self.run:
                for function in self.errbacks:
                    function(batch=self)
            raise e
        finally:
            self.unset()
        
        try:
            # Fire call backs after the batch succeeded
            if self.applied:
                for function in self.callbacks:
                    function()
            propagate(Event.UOW_END, sender=self, batch=self)
        except Exception as e:
            traceback.print_exc(e)

"""
Atom:
Unit of work for Accord Transactions in C*

```python

# ORM Style
account, profile, photo = None, None, None
try:
    pointer = Pointer(Profile, id="98e50d75-d025-4d4d-b99f-e08024ac44ec")
    with Atom() as atom:
        person = atom.var(pointer)

        # Conditional block begins and ends in this context manager.
        with atom.when(person.website == None):
            profile = Profile.create(name="John Doe", email="john.doe@example.com", phone="1234567890")
            account = Account.create(password="password", profile=profile)
            photo = Photo.create(profile=profile, blob=photo)
            Notification.create(user=profile.id, text=f"Welcome {profile.name}")

        # Add some more operations into the transaction, outside the conditional block
        author["name"] = "John Doe"
        author["email"] = "john.doe@example.com"
        author["phone"] = "1234567890"
        author["age"] = 30
        author["active"] = True
        author.save()                                              

except Exception as e:
    raise e
else:
    print("Transaction was successfully executed")
    return account, profile, photo
```
"""

class Atom(threading.local):
    """An atomic (transactional) unit of work which works with your Models"""
    open: bool 
    context: Dict[str, Any]
    transaction: "Transaction"
    trash : Set[Union["Entity", "Pointer"]]
    
    def __init__(self, **context):
        """Create a Transaction object"""
        self.open = False 
        self.context = context
        self.condition = None
        self.keyspace = context.get("keyspace", keyspace())
        self.transaction = Transaction(keyspace=self.keyspace)
        self.callbacks = []
        self.errbacks = []
        self.run = False
        self.error = False
        self.results = None 
        self.applied = False 
        self.trash = WeakSet()
        self.thread = threading.get_native_id()
    
    def var(self, value:Union["Pointer", "Entity", SelectQuery], name:str=None) -> Variable:
        """Create a variable for use in the transaction"""
        from cqlalchemy.core.models import Pointer, Entity
        if isinstance(value, Pointer):
            if not value.entity:
                raise ValueError("You must provide an entity for the Pointer")
            query = value.query()
            entity = value.entity 
        elif isinstance(value, Entity):
            if not value.saved():
                raise ValueError("You can only use saved entities as variables")
            query = value.key.query()
            entity = value
        elif isinstance(value, SelectQuery):
            query = value
            entity = value.entity
        else:
            raise ValueError("You must provide a Pointer, Entity or SelectQuery")
        
        if not name:
            name = f"var_{len(self.transaction.variables)}"
        variable = self.transaction.variable(name, query, entity)
        return variable
    
    def variable(self, value:Union["Pointer", "Entity", SelectQuery], name:str=None):
        """Same thing as using var() but with a different name"""
        return self.var(value, name)
    
    @manager
    def when(self, *expressions) -> Generator[Condition, None, None]:
        """Add a condition to the transaction"""
        if not self.open:
            raise CqlQueryException("You cannot add conditions to a closed transaction")
        if self.condition and not self.condition.closed:
            raise CqlQueryException("You cannot nest conditional blocks")
        self.condition = self.transaction.condition(*expressions)
        yield self.condition  # Yield to the caller to add queries to the condition
        self.condition.end()
    
    def invalidate(self, *instances):
        """Invalidate a Model instance"""
        from cqlalchemy.core.models import Pointer, Entity
        for instance in instances:
            if not isinstance(instance, (Pointer, Entity)):
                raise ValueError("You must provide an instance of an Entity or a Pointer")
            self.trash.add(instance)
        
    def add(self, query: Union[InsertQuery, UpdateQuery, DeleteQuery]):
        """Add a query to the transaction"""
        if not self.open:
            raise CqlQueryException("You cannot add queries to a closed transaction")
        if not query:
            raise ValueError("You must provide a query")
        if not isinstance(query, (str, InsertQuery, UpdateQuery, DeleteQuery)):
            raise ValueError("You must provide a valid query")
        if self.condition and not self.condition.closed:
            self.condition.then(query)
        else:
            self.transaction.add(query)
    
    @classmethod
    def get(self):
        """Returns the current atom for this thread or None"""
        thread = Local.instance()
        atom = getattr(thread, "atom", None)
        return atom

    def set(self):
        """Attempt to set this transaction as the transaction for the current thread"""
        previous = self.get()
        if previous and previous != self:
            raise IllegalStateException("You cannot have two active Transaction objects in a thread")
        thread = Local.instance()
        if hasattr(thread, "batch") and thread.batch:
            raise IllegalStateException("You cannot combine transactions and batches")
        self.open = True
        thread.atom = self

    def unset(self):
        """Attempt to unset this transaction as the transaction for the current thread"""
        previous = self.get()
        if previous and previous != self:
            raise IllegalStateException(
                "You cannot remove the Atom object for another context"
            )
        elif previous and previous == self:
            thread = Local.instance()
            thread.atom = None
        else:
            pass 

    def after(self, callbacks:List[Callable]):
        """Add callback hooks after the `successful` execution of this batch"""
        if callbacks and isinstance(callbacks, list):
            self.callbacks.extend(callbacks)

    def failure(self, errbacks:List[Callable]):
        if errbacks and isinstance(errbacks, list):
            self.errbacks.extend(errbacks)

    def __enter__(self):
        """Changes the current Thread Local Transaction to this object"""
        if self.run:
            raise IllegalStateException("You cannot enter a transaction that has already been run")
        self.set()
        return self

    def __exit__(self, *arguments, **kwds):
        """Execute the Transaction upon exit"""
        if not self.run:
            self.commit()
        self.unset()
    
    def commit(self):
        """Execute the Transaction"""
        from cqlalchemy.core.models import Model
        try:
            self.set()
            if not self.open:
                raise IllegalStateException("Your transaction is not open")
            self.transaction.execute()
            self.open = False
            self.results = self.transaction.results
            self.applied = True # True by default. 
            self.run = True 
        except Exception as e:
            self.exception = e
            self.error = True
            self.open = False
            self.applied = False
           
            if not self.run:
                for function in self.errbacks:
                    function(atom=self)
            raise e
        finally:
            self.unset()
        
        try:
            # Fire call backs after the atom executed without exception 
            if self.applied:
                for function in self.callbacks:
                    function()
            # Invalidate all the objects involved in this Atom.
            if self.trash:
                for instance in self.trash:
                    if isinstance(instance, Model):
                        instance.invalidate()
            propagate(Event.UOW_END, sender=self, atom=self)
        except Exception as e:
            traceback.print_exc(e)

       



"""
Session:
A collective unit of work boundary for managing different execution contexts within your application.
Session works with Batches, and Accord Transactions to persist multiple entities at once. 

It also acts as an identity map to prevent multiple instances of the same entity from 
being mutated across different contexts.

Session is threadsafe.
"""

class Session(object):
    """Collective Unit of Work Boundary & Identity Map"""
    closed : bool
    previous : "Session"
    lock : "Lock"
    updates : Dict["Pointer", "Entity"]
    objects : Dict["Pointer", "Entity"]
    deletions : Set["Pointer"]

    def __init__(self):
        self.closed = False
        self.previous = None
        self.objects = WeakValueDictionary()
        self.updates = OrderedDict()
        self.deletions = set()
        self.lock = RLock()
    
    def query(self, cls:Type["Entity"]) -> Union["CollectionQuery", "SelectQuery"]:
        """Builds a CQL query that uses this Session"""
        from cqlalchemy.core.models import Expando, Array, SortedSet, Model
        
        if issubclass(cls, (Expando, Array, SortedSet)):
            return CollectionQuery(entity=cls, session=self)
        elif issubclass(cls, Model):
            return SelectQuery(entity=cls, session=self)
        else:
            raise ValueError("You must provide a Model, Expando, Array or SortedSet")
    
    def contains(self, entity: Union["Pointer", "Entity"]) -> bool:
        """Returns True if the entity is in the session"""
        from cqlalchemy.core.models import Pointer, Entity
        if self.closed:
            raise IllegalStateException("You cannot check if an entity is in a closed session")

        if not isinstance(entity, (Entity, Pointer)):
            raise ValueError("You must provide an Entity or Pointer")

        key = Pointer.create(entity) if isinstance(entity, Entity) else entity
        if key in self.deletions:
            return True 
        if key in self.updates.keys():
            return True 
        if key in self.objects.keys():
            return True 
        return False 

    def bind(self, entity: "Entity"):
        """Binds an entity to this Session's object cache. This is useful for objects you retrieve from the database."""
        from cqlalchemy.core.models import Pointer, Entity

        if self.closed:
            raise IllegalStateException("You cannot bind an entity to a closed session")
        if not isinstance(entity, Entity):
            raise ValueError("You can only bind instances of an Entity to a Session")

        with self.lock:
            key = Pointer.create(entity)
            self.objects[key] = entity
            entity.session = self
    
    def add(self, entity: "Entity"):
        """Adds an entity to the session"""
        from cqlalchemy.core.models import Pointer, Entity
        if self.closed:
            raise IllegalStateException("You cannot add an entity to a closed session")

        with self.lock:
            if not isinstance(entity, Entity):
                raise ValueError("You can only add instances of an Entity to a Session")
            key = Pointer.create(entity)
            self.updates[key] = entity
    
    def delete(self, key:Union["Pointer", "Entity"]):
        """Marks an entity for deletion from the database when the session is committed"""
        from cqlalchemy.core.models import Pointer, Entity
        
        if self.closed:
            raise IllegalStateException("You cannot delete an entity from a closed session")
        
        with self.lock:
            key = Pointer.create(key) if isinstance(key, Entity) else key 
            if isinstance(key, Pointer):
                if key in self.objects:
                    del self.objects[key]
                if key in self.updates:
                    del self.updates[key]
                self.deletions.add(key)
            else:
                raise ValueError("You must provide a Pointer or Entity")

    def expunge(self, key:Union["Pointer", "Entity"]):
        """Disconnects an entity from the Session entirely."""
        from cqlalchemy.core.models import Pointer, Entity
        
        if self.closed:
            raise IllegalStateException("You cannot remove an entity from a closed session")

        with self.lock:
            key = Pointer.create(key) if isinstance(key, Entity) else key 
            if isinstance(key, Pointer):
                if key in self.objects:
                    del self.objects[key]
                if key in self.updates:
                    del self.updates[key]
                if key in self.deletions:
                    self.deletions.remove(key)
            else:
                raise ValueError("You must provide a Pointer or Entity")
    
    def get(self, key:Union["Pointer"]):
        """Returns an entity from the session by key, fetching it from the database if necessary (triggers a flush)"""
        from cqlalchemy.core.models import Pointer 

        if self.closed:
            raise IllegalStateException("You cannot get an entity from a closed session")
        
        # First, if there are any pending operations in this session, flush them to the database 
        # and refresh all the objects known to this session, before attempting to read anything from the session. 
        # This ensures that changes made in this session or other sessions are visible before you attempt to 
        # read from the session.
        with self.lock:
            if self.dirty:
                self.flush()                

            if isinstance(key, Pointer):
                entity = self.objects.get(key, None)        # Try to get entity from objects cache if it is there
                if not entity:
                    entity = key.get()                      # Fetch from database if not found in cache
                    self.bind(entity)
                return entity
            else:
                raise ValueError("You must provide a Pointer to an Entity")
    
    def cache(self, key:Union["Pointer"]):
        """Returns an entity from the session object cache, without checking the database (triggers a flush)"""
        from cqlalchemy.core.models import Pointer 

        if self.closed:
            raise IllegalStateException("You cannot get an entity from a closed session")

        with self.lock: 
            if self.dirty:
                self.flush()                       
            if isinstance(key, Pointer):                            
                return self.objects.get(key, None)        # Try to get entity from objects cache if it is there
            else:
                raise ValueError("You must provide a Pointer to an Entity")
    
    def refresh(self, entity:"Entity"):
        """Reload an Entity from the database, discarding any unsaved local operations on the entity, and invalidating the previous instance."""
        from cqlalchemy.core.models import Pointer, Entity
        
        if self.closed:
            raise IllegalStateException("You cannot refresh an entity from a closed session")
        if not self.contains(entity):
            raise ValueError("You can only refresh an entity that is in the session")

        with self.lock:
            if isinstance(entity, Entity):
                key = Pointer.create(entity)
                if key in self.objects or key in self.updates:
                    previous = entity 
                    cls = entity.__class__
                    entity = cls.read(key)
                    self.bind(entity)
                    if key in self.updates:
                        del self.updates[key]
                    previous.invalidate()   
                    return entity
                else:
                    raise ValueError("Entity not found in Session")
            else:
                raise ValueError("You must provide an Entity")
    
    def wire(self, provider:Union[Atom, Batch]):
        """Connects this Session to an Atom or Batch object for state tracking and management."""
        from cqlalchemy.core.models import Entity
        
        def execute_after_work(sender, **keywords):
            atom : Atom = keywords.get("atom", None)
            batch : Batch = keywords.get("batch", None)
            if debug():
                print("\n")
                print("Received Signal (UOW_END)")
                print("=========================")
                print("Atom : %s" % atom)
                print("Sender: %s" % sender)
                print("Batch : %s" % batch)
                print("\n")
            with self.lock:
                if atom is not None:
                    for value in atom.trash:
                        if isinstance(value, Entity):
                            pointer = value.key 
                            if pointer in self.objects:
                                self.refresh(value)
                elif batch is not None:
                    for value in batch.objects:
                        if isinstance(value, Entity):
                            pointer = value.key 
                            if pointer in self.objects:
                                self.refresh(value)
                else:
                    pass 
        subscribe(Event.UOW_END, execute_after_work, sender=provider)
        
    def save(self):
        """Commits all pending operations for the entities in the session"""
        if self.closed:
            raise IllegalStateException("You cannot save from a closed session")

        with self.lock:
             # Second, check if we are allowed to flush, if we are not raise an Exception
            isolated: bool = False 
            atom, batch, context = Atom.get(), Batch.get(), None 

            if atom and batch:
                raise IllegalStateException("You cannot use Atom and Batch together")
            elif atom is None and batch is None: 
                context = Batch.create(BatchType.Normal, keyspace())
                isolated = True
            elif atom is None and batch:
                context = batch
                self.wire(context)
            else:
                context = atom
                self.wire(context)

            try:
                if isolated:
                    context.set()
                # Save all the objects, and make all the deletions.
                for key, entity in self.updates.items():
                    entity.save()
                    self.bind(entity)
                for entity in self.objects.values():
                    entity.save()
                for key in self.deletions:
                    key.delete()
                
                if isolated:
                    context.execute()
            except Exception as e:
                raise e
            else:
                self.updates.clear()
                self.deletions.clear()
            finally:
                if isolated:
                    context.unset()
                

    def flush(self) -> bool:
        """Execute all pending operations, then reload all objects in the session."""
        with self.lock:
            # There are no pending operations, so we are done.
            if not self.dirty:
                return False                                         
            # Second, check if we are allowed to flush, if we are not raise an Exception
            atom, batch = Atom.get(), Batch.get()
            if atom is not None:
                raise IllegalStateException("You cannot flush from within an on-going transaction")
            if batch is not None:
                raise IllegalStateException("You cannot flush from within an on-going batch")
            
            # Third, create a new Batch and flush all the updates and deletes to it. 
            try:
                context = Batch.create(BatchType.Normal, keyspace())
                with context:
                    for key in self.deletions:
                        key.delete()
                        if key in self.objects:
                            del self.objects[key]
                        if key in self.updates:
                            del self.updates[key]
                    for key, entity in self.updates.items():
                        entity.save()
                        self.bind(entity)
            except Exception as e:
                raise e
            else:
                self.updates.clear()
                self.deletions.clear()
            
            # Finally update all the entities in the object cache/known to this session, so that 
            # changes made by other sessions are visible
            for key, entity in self.objects.items():
                self.refresh(entity)
            return True

    @property
    def dirty(self):
        """Returns True if there are any uncommitted changes to the objects in this Session"""
        from cqlalchemy.core.differ import changed

        with self.lock:
            if self.deletions:
                return True
            if self.updates:
                return True 
            for entity in self.objects.values():
                if changed(entity):
                    return True
            return False

    def close(self):
        """Closes the session, and release underlying resources used by the session"""
        if self.dirty:
            raise IllegalStateException("There are uncommitted changes in this Session. Did you forget to call save()?")
        with self.lock:
            self.closed = True
            self.clear()
    
    def clear(self):
        """Clears all entities from the session"""
        with self.lock:
            self.objects.clear()
            self.updates.clear()
            self.deletions.clear()
    
    def __enter__(self):
        """Changes the current Thread Local Session to this object"""
        if self.closed:
            raise IllegalStateException("You cannot enter a session that has already been closed")

        with self.lock:
            thread = Local.instance()
            session = getattr(thread, "session", None)
            self.previous = session
            thread.session = self
        return self

    def __exit__(self, *arguments, **kwds):
        """Execute the Session upon exit"""
        with self.lock:
            thread = Local.instance()
            session = getattr(thread, "session", None)
            if session is self:
                thread.session = self.previous
                self.previous = None
                self.close()
            else:
                raise IllegalStateException("This session is not currently bound to the current thread")
    
    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop('lock', None)
        return state
    
    def __setstate__(self, state):
        self.__dict__.update(state)
        self.lock = RLock()
        
    