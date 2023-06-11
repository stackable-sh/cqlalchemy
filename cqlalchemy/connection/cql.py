
import logging
from cassandra import ConsistencyLevel
from cassandra.query import SimpleStatement

from cqlalchemy.options import debug, verbose, keyspace
from cqlalchemy.core.builtins import Local, Global
from cqlalchemy.connection import functions

class CqlQueryException(Exception):
    """An Error that signifies that something bad happened during a CqlQuery"""
    pass


class Consistency(object):
    '''Context Manager Implementation for controlling Apache Cassandra Consistency Level on a Thread Local basis.'''
    def __init__(self, level):
        self.level = level
        self.previous = None
        
    def __enter__(self):
        '''Changes the current Thread Local Consistency Level'''
        local = Local.instance()
        if hasattr(local, "consistency"):
            self.previous = local.consistency 
        local.consistency = self.level
        
    def __exit__(self, *arguments, **kwds):
        '''Reverts the Thread Local Consistency Level to the previous value'''
        local = Local.instance()
        if self.previous:
            local.consistency = self.previous

'''
Level:
Allows you to control Thread Local consistency level as you use CQLAlchemy 
for various things; for example - 

with Level.Quorum:
    # Do some stuff here.
    
with Level.All:
    # Do some highly consistent thing here.
'''
class Level(object):
    '''Manages Different Consistency Levels'''
    Any = Consistency(ConsistencyLevel.ANY)
    All = Consistency(ConsistencyLevel.ALL)
    Quorum = Consistency(ConsistencyLevel.QUORUM)
    One = Consistency(ConsistencyLevel.ONE)
    Two = Consistency(ConsistencyLevel.TWO)
    Three = Consistency(ConsistencyLevel.THREE)
    LocalQuorum = Consistency(ConsistencyLevel.LOCAL_QUORUM)
    EachQuorum = Consistency(ConsistencyLevel.EACH_QUORUM)
    Serial = Consistency(ConsistencyLevel.SERIAL)
    LocalSerial = Consistency(ConsistencyLevel.LOCAL_SERIAL)
    LocalOne = Consistency(ConsistencyLevel.LOCAL_ONE)


class CqlQuery(object):
    """An object that can execute CQL queries on Apache Cassandra and return results"""
    
    def __init__(self, query, keyspace=None, idempotent=False):
        '''Every CqlQuery object requires a string query'''
        self.keyspace = keyspace
        self.query = query
        self.results = None
        self.idempotent = idempotent
        self.executed = False
    
    def execute(self, **keywords):
        """Executes the query associated with this object"""
        try:
            if not self.query:
                raise CqlQueryException("Please set the query attribute of CqlQuery before you proceed")
            world = Global.instance() # Get a hold of the shared global object
            if not world.connected:
                raise RuntimeError("You are not connected to Apache Cassandra")
            thread = Local.instance()
            if not hasattr(thread, "consistency"):
                thread.consistency = ConsistencyLevel.LOCAL_ONE

            if self.keyspace:
                world.session.set_keyspace(self.keyspace)
            statement = SimpleStatement(
                self.query, 
                is_idempotent=self.idempotent,
                consistency_level=thread.consistency,
                serial_consistency_level=ConsistencyLevel.SERIAL
            )
            self.results = world.session.execute(statement, trace=debug())
            self.executed = True
            return self
        except Exception as e:
            raise e
    
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
    if query.results:
        return query.results
    else:
        return None

"""
AutoCqlQuery:
Allows you build SELECT based queries that respects Model and their Descriptors. 
For example: 

``` python
from cqlalchemy import Model, UUID, String, Float, LT

class Book(Model):
    isbn = String(key=True, primary=True)
    name = String(index=True, required=True)
    pages = Integer(required=True, index=True)
    cover = Blob(required=False)
    description = String(length=250, required=True, index=True)

# ... insert some book objects into the datastore 
    
query = Book.objects.where(name="War & Peace", pages=LTE(100))
query.distinct("name","isbn")
query.order('isbn', desc=True)
query.limit(10)

# Use the explicit filter flag to ask Apache Cassandra to run this query even if it is expensive. 
query.execute(filter=True) 
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
results = Price
    .objects
    .columns("id", "book", "date, "currency", min("amount"))
    .group("book")
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
    .avg("price")\
    .where(book=book)\
.execute(filter=True)

print(result.get()["price"])
```

We will now attempt to count all the price objects we have stored

```python
result = Price
    .objects
    .count()
.execute(filter=True)

print("Price Objects: %s" % result.get())
```

Finally, let us count all the books that have a cover image set. 

```python
result = Book
    .objects
    .count("cover")
.execute()
print("Price Objects: %s" % result.get())
```

"""
class AutoCqlQuery(CqlQuery):
    '''A CqlQuery object that uses the builder pattern and understands Models'''
    
    def __init__(self, model):
        '''Initialize your AutoCqlQuery by passing the class the query needs.'''
        from cqlalchemy.core.models import CqlProperty, Entity
        from cqlalchemy.core.builtins import fields

        if not isinstance(model, Entity):
            raise CqlQueryException("You can only use Model-like objects on AutoCqlQuery")
        super(AutoCqlQuery, self).__init__(query=None)

        self.model = model
        self._columns_ = set()
        self._default_fetch_size_ = 1000
        self._properties_ = fields(self.kind, CqlProperty)
        self._template_ = "SELECT {distinct} {count} {columns} FROM {keyspace}.{kind} {where} {group} {order} {limit} {filter}"
        self._distinctive_, self._distinct_ = False, ""
        self._countable_, self._count_ = False, ""
        self._limitable_, self._limit_ = False, ""
        self._orderable_, self._order_ = False, dict()
        self._groupable_, self._group_ = False, set()
        self._whereable_, self._where_ = False, ""
        self._filterable_, self._filter_ = False, ""
        
    def _build_(self):
        '''Builds the Query object for execution'''
        if not self._limitable_: 
            self.limit(self._default_fetch_size_)

        if self._distinctive_:
            if self._countable_:
                raise CqlQueryException("You may not use COUNT and DISTINCT in the same query")
            if self._columns_:
                raise CqlQueryException("You may not use SPECIFIC COLUMNS/AGGREGATES and DISTINCT in the same query")
            columns, count, distinct = "", "", self._distinct_
        elif self._countable_:
            if self._distinctive_:
                raise CqlQueryException("You may not use COUNT and DISTINCT in the same query")
            if self._columns_:
                raise CqlQueryException("You may not use COUNT and SPECIFIC COLUMNS in the same query")
            columns, count, distinct = "", self._count_, ""
        elif self._columns_:
            if self._countable_:
                raise CqlQueryException("You may not use COUNT, and SPECIFIC COLUMNS/AGGREGATES in the same query")
            if self._distinctive_:
                raise CqlQueryException("You may not use SPECIFIC COLUMNS/AGGREGATES and DISTINCT  in the same query")
            columns, count, distinct = ",".join(self._columns_), "", ""
        else:
            columns, count, distinct = "*", "", ""
            
        query = self._template_.format(
            distinct=distinct, 
            count=count,
            columns=columns,
            keyspace=self.model.keyspace(), 
            kind=self.model.kind(), 
            where=self._where_, 
            group=self._build_group_(),
            order=self._build_order_(), 
            limit=self._limit_, 
            filter=self._filter_
        )
        self.query = query.strip()
        return self
    
    def _build_group_(self):
        """Builds the GROUP BY part of the query"""
        pass 
        if self._groupable_:
            pattern = "GROUP BY {names}"
            result = pattern.format(",".join(self._group_))
            return result 
        else:
            return ""

    def _build_order_(self):
        """Builds the ORDER BY part of the query"""
        result, started =  "", False
        if self._orderable_:
            for name in sorted(self._order_.keys()):
                direction = self._order_[name]
                if not started:
                    pattern = "ORDER BY {name} {direction}"
                    result += pattern.format(name=name, direction=direction)
                    started = True
                else:
                    pattern = ", {name} {direction}"
                    result += pattern.format(name=name, direction=direction)
            return result
        else:
            return ""
    
    def _parse_where_(self, keywords):
        '''An internal helper method for query and count'''
        from cqlalchemy.core.models import Operator, EQ
        properties = self._properties_
        extension = ""
        for name, value in list(keywords.items()):
            property = properties.get(name, None) 
            if not property:
                raise CqlQueryException("The %s Property doesn't exist on: %s" % (name, self.model))
            if not property.key or not property.indexed():
                raise CqlQueryException("You can only use WHERE on keys and kndexed properties: %s" % (name))
            part = ""
            if isinstance(value, Operator):
                if value.right is None: 
                    raise ValueError("Your Operator must have its RHS set to be valid")
                operator = value
                operator.model = self.model
                operator.left = name
                part = str(operator)
            else:
                #If no operator set, assume EQ 
                operator = EQ(right=value)
                operator.left = name
                operator.model = self.model
                part = str(operator)
                    
            if not self._whereable_:
                extension += "WHERE {part}".format(part=part)
                self._whereable_ = True
            else:
                extension += " AND {part}".format(part=part)
        return extension
    
    def _allow_filtering_(self):
        '''Adds the ALLOW FILTERING clause to the internal query template'''
        if not self._filterable_:
            self._filter_ = "ALLOW FILTERING"
            self._filterable_ = True
        return self

    def order(self, name, asc=True, desc=False):
        '''Adds the ORDER BY to the Query'''
        if not asc and not desc:
            raise CqlQueryException("You must provide either the asc or desc keyword arguments")
        if asc and desc:
            raise CqlQueryException("You cannot use both ASC and DESC in the same query")
        property = self._properties_.get(name, None)
        if not property or not property.key:
            raise CqlQueryException("Property: %s does not exist or is not a clustering key" % name)
        direction = "ASC" if asc else "DESC"
        self._order_[name] = direction
        self._orderable_ = True
        return self
    
    def group(self, *names):
        """Adds GROUP BY to the Query"""
        # Cassandra only allows you to group by key
        for name in names:
            if name not in self._properties_:
                raise CqlQueryException("{name} does not exist within {kind}".format(name=name, model=self.model.kind()))
            descriptor = self._properties_[name]
            if not hasattr(descriptor, "key") or getattr(descriptor, "key", False):
                raise CqlQueryException("{name} is not a primary or clustering Key".format(name=name))
            if descriptor.key is True:
                self._group_.add(name)
        if self._group_:
            self._groupable_ = True 
        return self
    
    def where(self, **keywords):
        '''Dynamically builds the WHERE clause from **keywords'''
        self._where_ = self._parse_where_(keywords)
        return self
    
    def count(self, name):
        '''Builds the COUNT(*) section of the internal template'''
        if self._distinctive_:
            raise CqlQueryException("You cannot use the DISTINCT and COUNT clause in the same query")
        if name:
            self._count_ = f"COUNT({name})"
        else:
            self._count_ = "COUNT(*)"
        self._countable_ = True
        return self
        
    def limit(self, value):
        '''LIMIT for the query'''
        self._limit_ = "LIMIT {value}".format(value=value)
        self._limitable_ = True
        return self
    
    def ttl(self, name, alias=None):
        """TTL for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"There is no property called {name} on {self.model.__name__}")
        part = str(functions.ttl(name, alias))
        self._columns_.append(part)
        return self

    def writetime(self, name, alias=None):
        """WRITETIME for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"There is no property called {name} on {self.model.__name__}")
        part = str(functions.writetime(name, alias))
        self._columns_.append(part)
        return self

    def avg(self, name, alias=None):
        """AVG for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"There is no property called {name} on {self.model.__name__}")
        part = str(functions.avg(name, alias))
        self._columns_.append(part)
        return self

    def max(self, name, alias=None):
        """MAX for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"There is no property called {name} on {self.model.__name__}")
        part = str(functions.max(name, alias))
        self._columns_.append(part)
        return self

    def min(self, name, alias=None):
        """MIN for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"There is no property called {name} on {self.model.__name__}")
        part = str(functions.min(name, alias))
        self._columns_.append(part)
        return self

    def sum(self, name, alias=None):
        """SUM for the @name property"""
        if name not in self._properties_:
            raise ValueError(f"There is no property called {name} on {self.model.__name__}")
        part = str(functions.sum(name, alias))
        self._columns_.append(part)
        return self
    
    def columns(self, *names):
        """Allows you to select a specific set of columns from the Table"""
        for name in names:
            if isinstance(name, str):
                if name not in self._properties_:
                    raise ValueError(f"There is no property called {name} on {self.model.__name__}")
                self._columns_.add(name)
            elif isinstance(name, functions.Function):
                self._columns_.add(name())
            else:
                raise ValueError(f"Parameter {name} must be an instance of str, or a CQL Function")
        return self

    def distinct(self, *names):
        '''Adds the DISTINCT clause to the query'''
        properties = self._properties_
        for name in names:
            property = properties.get(name, None)
            if not property:
                raise CqlQueryException("Property: {name} does not exist in {model}".format(name=name, model=self.model))
            if not property.key or not property.static:
                raise CqlQueryException("You can only use the DISTINCT clause on key and static properties")
            if not self._distinctive_:  
                part = "DISTINCT {names}".format(names=",".join(names))
                self._distinct_ = part
                self._distinctive_ = True
            else:
                part = ",".join(names)
                self._distinct_ = part
        return self
        
    def execute(self, filter=False):
        """Executes the query applying ALLOW FILTERING if required"""
        if filter:
            self._allow_filtering_()
        self._build_()
        return super(AutoCqlQuery, self).execute()
    
    def first(self):
        """Returns the first result of the query"""
        pass
    
    def get(self):
        """Returns the result for the query."""
        try:
            return next(iter(self))
        except StopIteration:
            return None

    def all(self):
        """Returns a list which contains all the results of a query"""
        return list(self)
    
    def one(self):
        """Expects, and returns only one result, any more results will throw a ResultException"""
        data = self.all()
        if len(data) > 1:
            raise CqlQueryException("Fetched more than a single object")
        return data[0]



"""
Batch:

Allows you to execute many related C* operations in one network request. 
We provide support for LOGGED, UNLOGGED, and COUNTER Batch objects through the BatchType Enum. 

```python
from cqlalchemy import Model, Batch, String, BatchType

class Book(Model, version=True):
    name = String(index=True, required=True)
    author = String(index=True, required=True) 

with Batch: 
    Book.create(name="The Great Gasby", author="F. Scott Fitzgerald")
    Book.create(name="The Adventures of Huckleberry Finn", author="Mark Twain")
    Book.create(name="To Kill a Mockingbird", author="Harper Lee")

    
# Use BatchType.Counter & BatchType.Unlogged for COUNTER, and UNLOGGED Batch queries. 

Analytics = Counter("Analytics", ["books",])

with Batch(BatchType.Counter):
    stats = Analytics.create(id="com.amazon.books")
    stats.incr("books", 3)
```
"""
class Batch(object):
    """Execute multiple queries in a single network request to get per partition isolation."""
    pass 