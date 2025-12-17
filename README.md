Description
===========
CQLAlchemy is a powerful, intuitive, beautiful and pragmatic toolkit for [Apache Cassandra 5.0.0+](http://cassandra.apache.org) 
inspired by Michael Bayer's excellent SQLAlchemy, and the original implementation of the storage APIs in Google App Engine 
for Python (Memcached & Datastore).

It uses Martin Fowler's (Unit of Work Pattern)[https://martinfowler.com/eaaCatalog/unitOfWork.html]
to track the changes you make to your entities, then saves those changes by emitting the appropriate updates 
sequentially to Cassandra by using a new batch  (or joining the existing batch open batch).

The hardest part of using Apache Cassandra is arguably the shift in mindset required to build a working `data model`; 
we designed CQLAlchemy to take the pain away from that process by abstracting away the hard parts, and providing guard rails
to prevent you from using common anti-patterns. 

CQLAlchemy effectively allows your engineering team to save development hours, standardize on Apache Cassandra, 
improve the performance of your app, and save on cloud infrastructure costs - without handling or worrying about 
all the nuts, bolts, and quirks of using Apache Cassandra in your day to day work.

CQLAlchemy has excellent test coverage (actual tests against C*, not mocked), and is production ready.

Batteries Included
==================
Apart from a powerful, configurable, expressive object non-relational mapper, a rich set of data descriptors 
which provide coercion, validation, and serialization for common usecases; CQLAlchemy also ships with 
production ready batteries for:

1. Model : Entity object mapping with intuitive and rich query functionality.
2. Common Descriptors : Rich and robust library of common descriptors, including collections (Map, Set, List, Tuple).
3. Expando : A dynamically expandable, fast, durable and queryable Map-like entity backed by C* for friendly wide rows.
4. Array : durable ordered one dimensional Array object backed by C*. 
5. SortedSet : A performant, durable, queryable, sorted Set backed by C*
6. Distributed Counters : High Level Abstraction for C* backed durable Counter objects.
7. Cache : Performant, durable and always-hot cache built on C*, for your in-memory caching needs.
8. Versioning : Infinite client side historical change tracking, revision & point-in-time restore and rollbacks.
9. Transactions: Intuitive Support for LWT, and Accord Transactions in C*
10. Serialization : Production grade JSON serialization powered by [Marshmallow](https://marshmallow.readthedocs.io)


Quickstart
==========
This example walks you through creating a simple entity, and persisting through cqlalchemy. 


```python
# Relevant imports.

import cqlalchemy
from cqlalchemy import UUID, String, Email, DateTime
from cqlalchemy import Model

cqlalchemy.configure(keyspace="Example", servers=["127.0.0.1",], port=9042)

# Create a model (with change tracking enabled) for storing user profiles.

class Profile(Model, version=True): 
    id = UUID(primary=True)
    name = String(required=True)
    email = Email(required=True, index=True)
    created = DateTime(now=True)

person = Profile.create(name="Peter Parker", email="peter@marvel.com")
print(person.saved())

"""
This creates a new Keyspace named 'Example', and a new Table called 'Profile' (with change tracking enabled), 
and stores a new profile row object within it. Next, we will attempt to read the object back from 
Cassandra using the primary key. 
"""

key = person.key
instance = Profile.read(key)
assert person == instance

# Next, we will attempt to find an object using the secondary index automatically created by cqlalchemy"""
instance = (Profile
    .objects
    .where(email="peter@marvel.com")
.get())
assert instance == person

# Next, we will attempt to count all the objects we have stored so far"""
assert Profile.objects.count() == 1

# Next, we will iterate through all the stored objects and print out their names"""
for instance in Profile.objects.all():
    print(f"Hello {instance.name}!")

# Finally, let's clean up by removing the object we just created"""
Profile.delete(key)
```

Notice that cqlalchemy automatically handles connections, pooling, batching, creating tables, syncing them,
and everything else required - quietly and under the hood. You can learn more about how to use CqlAlchemy 
by visiting the documentation. 





