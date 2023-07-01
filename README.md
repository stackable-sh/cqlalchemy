Description
===========
CQLAlchemy is an intuitive, beautiful and pragmatic database toolkit for [Apache Cassandra 4.1+](http://cassandra.apache.org) 
inspired by Michael Bayer's excellent SQLAlchemy, and the original implementation of the storage APIs in 
Google App Engine for Python (Memcached & Datastore). 

CQLAlchemy has excellent test coverage (actual tests against C*, not mocked), and is production ready.


Quickstart
==========
This example walks you through installing cassandra, starting it, and creating a simple model, 
and persisting through cqlalchemy. 


```python
# Relevant imports.
from datetime import datetime

import cqlalchemy
from cqlalchemy import UUID, String, URL, Integer
from cqlalchemy import Model, Level

cqlalchemy.configure(keyspace="Example", servers=["127.0.0.1",], port=9042)

# Create a model for storing user profiles.

class Profile(Model): 
    id = UUID(key=True)
    name = String(required=True, index=True)
    email = String(required=True, index=True, nullable=False)
    age = Integer(index=True, required=True)
    created = DateTime(nullable=False, default=datetime.now())

person = Profile.create(name="Peter Parker", email="peter@marvel.com", age=16)
print(person.saved())

"""
This creates a new Keyspace named 'Example', and a new Table called 'Profile', and stores a new 
profile row object within it. Next, we will attempt to read the object back from Cassandra using a primary key. 
"""

# Read an object using their primary key
key = person.key
instance = Profile.objects.get(key)
assert person == instance

# Next, we will attempt to find an object using the secondary index automatically created by cqlalchemy"""
instance = Profile.objects.where(email="peter@marvel.com", age=LTE(18)).get()
assert instance == person

# Next, we will attempt to count all the objects we have stored so far"""
assert Profile.objects.count() == 1

# Next, we will iterate through all the stored objects and print out their names"""
for instance in Profile.objects.all():
    print(f"Hello {instance.name}!")

# Finally, let's clean up by removing the objects we just created"""
result = Profile.delete(key)
assert result == True
```
Notice that cqlalchemy automatically handles connections, pooling, batching, creating tables, syncing them,
and everything else required - quietly and under the hood.

Batteries Included
==================
Apart from a powerful, configurable, expressive object non-relational mapper, a rich set of data descriptors which provide coercion, validation, and serialization for common usecases; Cqlalchemy also ships with production ready batteries for:

1. Model : Entity object mapping with intuitive and rich query functionality.
2. Common Descriptors : Robust library for descriptors, including collections (List, Map, Set, Tuple, Email, URL, Phone etc)
3. Expando : A dynamically expandable, fast, durable and queryable Entity for wide rows.
4. Vector : durable ordered Vector|List|Stack object for C*, which supports LIFO (Stack) or FIFO (Queue) access patterns
5. Block : A performant, durable, queryable, unordered  Set backed by C*
6. Counter : High Level Abstraction for C* backed durable Counter objects.
7. Data Versioning : Infinite historical change tracking, revision & point-in-time restore (see Papertrail/Rails, Continuum/SQLAlchemy)
8. Cache : A fast, performant, durable and always-hot cache built on Cassandra, which solves your in-memory caching needs. 
9. Schema & Data Migrations: Safe, and reversible schema and data migrations. 
10. Fast, safe and easy JSON serialization/deserialization of Entity objects.

CqlAlchemy allows your engineering team to standardize on Apache Cassandra, improve the performance of your app, and save on cloud infrastructure costs - without handling or worrying about all the nuts, bolts, and quirks of Apache Cassandra. 

You can learn more about how to use CqlAlchemy by visiting the documentation. 



