"""
History
=======
This module provides client side change data capture, (infinite) historical data versioning 
and change revision for Entity objects. Simply put, you can revert changes that you have 
made to your entities, using this module. 

This module works behind the scenes (without your interference) on `Entity` objects which have been 
marked as versioned, to provide versioning


```python
import arrow

class Profile(Model, version=True):
    name = String(index=True, required=True)
    gender = String(choices=('M', 'F',))

person = Profile.create(name="Iroiso", gender='M')         # Create v1.0 of the object
person.name = "Jennifer Watts"                             # Change the object, and save it to create a v2.0 
person.gender = 'F'
person.save()

person.name = "Jennifer Garner"
person.save()

previous = person.history[0]                               # Fetch the most recent change from the history property. 
print(previous["name"])                                    # You can access the state of the object as it was at v1.0
previous.revert()   

assert person.name == "Jennifer Watts"                     # Reverts the state of the object to v1.0
person.save()                                              # Explicitly save the object again to create v3.0
```
"""
from enum import Enum

from cqlalchemy.core.models import Model, Reference, UUID
from cqlalchemy.core.commons import Map, String, Pickle, DateTime, Choice

Edit = Enum("Edit", ["INSERT", "UPSERT", "UPDATE", "DELETE"])


class ChangeSet(Model, version=False):
    """Unit of Change"""

    id = UUID(primary=True, composite=["entity"])
    entity = Reference(Model, key=True, required=True)
    created = DateTime(key=True, now=True, order="DESC")
    state = Map(String, Pickle, required=True)
    operation = Choice(Edit, index=True, required=True)
    user = Reference(Model, index=True)
    previous = Reference("ChangeSet", index=True)
    next = Reference("ChangeSet", index=True)

    def revert(self):
        """Reverts the change on our Entity to our state"""
        pass
