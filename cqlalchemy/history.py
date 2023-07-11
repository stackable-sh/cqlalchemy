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

assert person.name == "Jennifer Watts"                     # Reverts the state of the object to v1.0 in C*
```
"""
from enum import Enum
from typing import Any, List

from cqlalchemy.core.builtins import fields
from cqlalchemy.connection.table import SchemaError, Schema
from cqlalchemy.core.models import Model, Reference, UUID, Entity, CqlProperty, Key, CounterModel, options
from cqlalchemy.core.commons import Map, String, Pickle, DateTime, Choice, Text, Set


Edit = Enum("Edit", ["INSERT", "UPSERT", "UPDATE", "DELETE", "REVERT"])


class RevisionError(Exception):
    """Generic Exception base class for History and Revision"""
    pass 

"""
ChangeSet

This is the unit of change. 

This model stores meta information about a versioned Entity just before it is saved to C*
so that we can recreate its exact state in the future. We store the previous state of the model 
the current set of changes, the underlying tracker diffs/operations, and then we store the final 
state of the Entity when you commit changes to it to the internal tracker. This information 
allows a ChangeSet to rewind an `Entity` to any state in the past. 

Only the owner entity, and their explicitly defined relationships (through the Reference descriptor) 
will be affected. 



```python
import arrow

class Profile(Model, version=True):
    name = String(index=True, required=True)
    gender = String(choices=('M', 'F',))

person = Profile.create(name="Jordan Lopez", gender='M')           # Create v1.0 of the object
person.name = "Jennifer Watson"                                    # Change the object, and save it to create a v2.0 
person.gender = 'F'
person.save()

previous = person.history[0]                               # Fetch the most recent change from the history property. 
print(previous["name"])                                    # You can access the state of the object as it was at v1.0
person = previous.revert()                                 # Reverts the state of the object to the state at v1.0, creating v3.0

assert person.name == 'Jordan Lopez'
assert person.gender == 'M'

print(person.history.last())                               # Returns the latest version of the object
print(person.history.first())                              # Returns the first version

timestamp = arrow.now().shift(hours=-24)
change = person.history.at(timestamp)                      # Returns the most recent change before `timestamp`
batch = change.batch 
print(change)

now = arrow.now()
start, end = now.date(), now.shift(days=-30)
                            
for change in person.history.span(start=start, end=end):   # To see changes over a particular period of time use `span`
    print(change)

history = History([instance,])                              
timestamp = arrow.now().shift(days=-45)
history.restore(to=timestamp)                               #  Rewind a group of objects/relations to `timestamp`
history.restore(to=batch)                                   #  Rewind all the changes in affected entities to state as of `batch`
```
"""

class ChangeSet(Model, version=False):
    """Unit of Change"""

    id = UUID(primary=True, composite=("entity",))
    entity = Reference(Model, key=True, required=True)
    created = DateTime(key=True, now=True, order="DESC")
    batch = String(index=True)
    previous = Map(String, Pickle)
    state = Map(String, Pickle)
    ops = Pickle(required=True)
    trackables = Map(String, Pickle)
    edit = Choice(Edit, index=True, required=True)
    user = Reference(Model, index=True)
    hash = String(index=True, required=True)
    comment = String(index=True)
    columns = Set(required=True, index=True)
    description = Text(index=True)

    def revert(self, description=""):
        """Reverts the change on our Entity to our state"""
        return Reverter(self.instance).revert(to=self, description=description)


class ChangeSetProxy(object):
    """Read only Object Proxy for a ChangeSet"""

    allowed = (
        "id",
        "created",
        "batch",
        "edit",
        "user",
    )

    def __init__(self, host: ChangeSet):
        self.host = host

    def __getitem__(self, key):
        return self.host.state.get(key, None)

    def __getattribute__(self, name: str) -> Any:
        if name in self.allowed:
            return getattr(self.host, name)
        else:
            raise AttributeError(f"Attribute access to {name} is not allowed")

    def __str__(self) -> str:
        state = {}
        if self.host.state:
            for name, value in self.host.state.items():
                diff = []
                diff.append(self.host.previous.get(name, None))
                diff.append(value)
                state[name] = diff 
        if self.host.previous:
            for name, value in self.host.previous.items():
                if name not in state:
                    diff = [value, None]
                    state[name] = diff 
        output = {
            "id": str(self.host.id),
            "created": str(self.host.created),
            "batch": self.host.batch,
            "edit": self.host.edit,
            "user": self.host.user,
            "state": str(state)
        }
        return str(output)



"""
Reverter
Knows how to revert a persisted entity to a ChangeSet from the past.
"""
class Reverter(object):
    """Rollback an Entity to a ChangeSet from the past"""

    def __init__(self, entity: Entity):
        if not issubclass(entity, Entity):
            raise SchemaError("You must provide a subclass of `Entity` to the Reverter")
        if issubclass(entity, CounterModel):
            raise SchemaError("Reverter does not support `Counter` entities")
        
        versioned = options(entity, "version", False)
        if not versioned:
            raise RevisionError("Your `Entity` does not support change revision")
        
        self.key = Key.create(entity)
        self.properties = fields(entity, CqlProperty)
        self.entity = entity
        self.created = False

    def refresh(self):
        """Synchronizes Schema of the entity with our internal schema"""
        if not self.created and not Schema.exists(self.entity):
            Schema.create(self.entity) 
            self.created = True
    
    def _change_(self, diff: ChangeSet, desc: str):
        """Reverts the underlying entity to the state of @diff"""
        columns = set(diff.columns)
        for name in columns:
            if name not in self.properties:
                raise RevisionError("Your `Entity` schema seems to have changed. Column: %s was not found" % name)


    def _delete_(self, diff: ChangeSet, desc: str):
        pass 

    def revert(self, to: ChangeSet, description: str=""):
        """Revise our host entity to the state in @to"""
        self.refresh()

        match to.edit:
            case (Edit.INSERT, Edit.UPDATE, Edit.UPSERT, Edit.REVERT):
                self._change_(diff=to, desc=description)
            case Edit.DELETE:
                self._delete_(diff=to, desc=description)
            case _:
                raise RevisionError("Received an Unsupported Edit: %s" % to.edit)



"""
History

Modify history for a group of (related) entities at the same time. Using this class, 
you can rewind objects to a particular point in time, or a particular batch transaction. 

Only the declared entities, and their explicitly defined relationships (through the Reference descriptor) 
will be affected. 


```python
import arrow

class Profile(Model, version=True):
    name = String(index=True, required=True)
    gender = String(choices=('M', 'F',))

person = Profile.create(name="Jordan Lopez", gender='M')           # Create v1.0 of the object
person.name = "Jennifer Watson"                                    # Change the object, and save it to create a v2.0 
person.gender = 'F'
person.save()

history = History([person, ])                              
timestamp = arrow.now().shift(days=-45)
history.restore(to=timestamp)                               #  Rewind a group of objects/relations to `timestamp`
history.restore(to=batch)                                   #  Rewind all the changes in affected entities to state as of `batch`
```
"""
class History(object):
    """Allows you to modify the history of a group of related objects"""
    def __init__(self, objects: List[Entity]):
        self.entities = objects
    
    def restore(self, to: str):
        """Restores the """
