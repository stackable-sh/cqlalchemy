Description
===========
Home is an intuitive and pragmatic database toolkit for [Apache Cassandra](http://cassandra.apache.org)


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

cqlalchemy.configure(keyspace = "Example", servers = ["127.0.0.1:9140",])

# Create a model for storing user profiles.

class Profile(Model): 
    id = UUID(key=True)
    name = String(required=True, index=True)
    email = String(required=True, index=True, nullable=False)
    age = Integer(index=True, required=True)
    created = DateTime(nullable=False, default=datetime.now())


person = Profile(name="Peter Parker", email="peter@marvel.com", age=16)
person.save()
key = person.id

"""
This creates a new Keyspace named 'Example', and a new Table called 'Profile', and stores a new profile row object within it.
Next, we will attempt to read the object back from Cassandra using it's primary key. 
"""

# Read an object using their primary key
instance = Profile.objects.get(id=key)
assert person == instance


"""Next, we will attempt to find an object using the secondary index automatically created by cqlalchemy"""


# Find the Profile whose email is 'peter@marvel.com' and whose age is less than 18
query = Profile.objects.where(email="peter@marvel.com", age=LTE(18))
instance = query.one()
assert instance == person

"""Next, we will attempt to count all the objects we have stored so far"""

# Let's count how many Profile objects we have stored. 
assert Profile.objects.count() == 1

"""Next, we will iterate through all the stored objects and print out their names"""

# Let's iterate through all the stored profile objects.
for instance in Profile.objects.all():
    print(f"Hello {instance.name}!")

```

Notice that cqlalchemy automatically handles connections, pooling, batch updates, and everything 
else required transparently under the hood. 

This project is production ready, and is heavily in use at Metro, a commercial bank for 
startups and founders in Africa. This is by no means a complete guide, dive into the documentation 
to quench your thirst. 
