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
import uuid
import copy
import warnings
from enum import Enum
from datetime import datetime
from typing import Any, List, Union

import arrow

from cqlalchemy.core.types import Container
from cqlalchemy.core.differ import Action, trackable, changes
from cqlalchemy.options import keyspace
from cqlalchemy.core.builtins import fields
from cqlalchemy.connection.table import SchemaError, Table
from cqlalchemy.core.commons import Map, String, Pickle, DateTime, Choice, Text, Set
from cqlalchemy.connection.functions import AND, LTE, GTE
from cqlalchemy.connection.cql import Batch, BatchType, execute
from cqlalchemy.core.models import (
    Model,
    Reference,
    Entity,
    Model,
    CounterModel,
    options,
    CqlProperty,
)


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
previous.revert()                                          # Reverts the state of the object to the state at v1.0, creating v3.0

person = Profile.refresh(person)
assert person.name == 'Jordan Lopez'
assert person.gender == 'M'

print(person.history.latest())                             # Returns the latest version of the object
print(person.history.oldest())                             # Returns the first version

timestamp = arrow.now().shift(hours=-24)
change = person.history.at(timestamp)                      # Returns the most recent change before `timestamp`
if change:
    change.revert()                                        # Revert the entity to that change

now = arrow.now()
start, end = now.date(), now.shift(days=-30)             
for change in person.history.span(start=start, end=end):   # To see changes over a particular period of time use `span`
    print(change)
```
"""


class ChangeSet(Model, version=False):
    """Unit of Change"""

    entity = Reference(Model, primary=True)
    created = DateTime(key=True, now=True, order="DESC")
    journal = String(required=True, index=True)
    previous = Map(String, Pickle)
    state = Map(String, Pickle)
    ops = Pickle()
    trackables = Map(String, Pickle)
    edit = Choice(Edit, index=True, required=True)
    user = Reference(Model, index=True)
    columns = Set(String, index=True)
    description = Text(index=True)

    def revert(self, description=""):
        """Reverts the change on our Entity to our state"""
        if not hasattr(self, "instance"):
            raise RevisionError("Provide a future instance of `Entity` to revise it.")
        return Reverter(self.instance).revert(to=self, description=description)


"""
BatchSet

A denormalized table that allows us to find all the objects changed in a particular
C* Batch without resorting to using ChangeSet.batch index, which will become expensive 
as usage increases over time. 
"""


class BatchSet(Model, version=False):
    """Stores ChangeSet by its entity, and the batch where it occurred"""

    entity: Model = Reference(Model, primary=True, composite=("journal"))
    journal: str = String(key=True)
    change: ChangeSet = Pickle(required=True)
    created: datetime = DateTime(required=True, now=True)


"""
Audit

A denormalized table that allows us to find all the objects changed by a particular 
user accross all time, providing simple but effective Audit Trails for CqlAlchemy
"""


class Audit(Model, version=False):
    """Stores action by user and the batch where it occurred"""

    user: Model = Reference(Model, primary=True, composite=("journal",))
    journal: str = String(key=True)
    edit: Edit = Choice(Edit, index=True, required=True)
    created: datetime = DateTime(key=True, now=True)
    change: ChangeSet = Pickle(required=True)


"""
capture

Implementation of change capture, which relies on our signaling mechanism to track
changes to entities as soon as they are committed to a batch.
"""


def capture(event, **keywords):
    """Creates a new ChangeSet in response to an Event"""
    if "key" in keywords:
        pointer = keywords.get("key")
        batch, edit = keywords.get("batch", None), keywords.get("edit")

        if options(pointer.kind, "version", False) and edit is Edit.DELETE:
            user = batch.context.get("user", None) if batch else None
            if user:
                if not isinstance(user, Model):
                    raise RevisionError(
                        "Provide an instance of Model for `user` in the Batch Context"
                    )
            table = pointer.table.title()
            guid = batch.guid if batch else str(uuid.uuid4())
            context = batch.context if batch else {}
            desc = f"{table}: Performed Operation {edit} in Batch: {guid}"
            with Batch(BatchType.Normal, **context):
                diff = ChangeSet.create(
                    entity=pointer,
                    journal=guid,
                    edit=edit,
                    user=user,
                    description=desc,
                )
                BatchSet.create(entity=pointer, journal=guid, change=diff)
                if user:
                    Audit.create(user=user, journal=guid, edit=edit, change=diff)
    else:
        entity, edit = keywords.get("entity"), keywords.get("edit")
        table = entity.table().title()
        if options(entity, "version", False) and edit in (Edit.INSERT, Edit.UPDATE, Edit.UPSERT):
            tracker = entity.__tracker__
            batch = keywords.get("batch")
            edit = keywords.get("edit")
            user = batch.context.get("user", None)
            if user:
                if not isinstance(user, Model):
                    raise RevisionError(
                        "Provide an instance of Model for `user` in the Batch Context"
                    )

            desc = f"{table}: Performed Operation {edit} in Batch: {batch.guid}"
            trackables = dict()
            for name, value in entity.__fields__.items():
                value = getattr(entity, "name", None)
                if trackable(value):
                    trackables[name] = list(changes(value))
            
            with Batch(BatchType.Normal, **batch.context):
                diff = ChangeSet.create(
                    entity=entity,
                    journal=batch.guid,
                    previous=copy.deepcopy(tracker.state),
                    state=copy.deepcopy(entity.__store__),
                    ops=copy.deepcopy(list(changes(entity))),
                    trackables=trackables,
                    edit=edit,
                    user=user,
                    columns=set(entity.__fields__.keys()),
                    description=desc,
                )
                BatchSet.create(entity=entity, journal=batch.guid, change=diff)
                if user:
                    Audit.create(user=user, journal=batch.guid, edit=edit, change=diff)
           
class ChangeSetProxy(object):
    """Read only Object Proxy for a ChangeSet"""

    allowed = (
        "id",
        "created",
        "journal",
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

    def revert(self, description=""):
        return self.host.revert(description=description)

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
            "journal": self.host.journal,
            "edit": self.host.edit,
            "user": self.host.user,
            "state": str(state),
        }
        return str(output)


"""
Reverter
Safely revert a persisted (and versioned) entity to any of its past committed states. 
"""


class Reverter(object):
    """Rollback an Entity to a ChangeSet from the past"""

    def __init__(self, entity: Entity):
        if not isinstance(entity, Entity):
            raise SchemaError(
                "You must provide an instance of `Entity` to the Reverter"
            )
        if isinstance(entity, CounterModel):
            raise SchemaError("Reverter does not support `Counter` entities")
        versioned = options(entity, "version", False)
        if not versioned:
            raise RevisionError("Your `Entity` does not support change revision")

        self.kind = entity.__class__
        self.table = Table(self.kind)
        self.entity = entity
        self.properties = self.table.properties

    def _revert_(
        self,
        entity: Model,
        diff: ChangeSet,
        desc: str,
        visited: set,
        commit: bool = True,
        relations: Union[bool, List[str]] = True,
        ignore: List[str] = [],
    ):
        """Recursively rollback a Model and its eligible children."""
        if not visited:
            visited = set()
        operations = self._rollback_(entity, diff, ignore=ignore)
        if relations:
            properties = fields(entity, CqlProperty)
            if isinstance(relations, bool):
                # If `relations` is True, then all the first level descriptors could be valid relations.
                relations_ = list(properties.keys())
            for name, descriptor in properties:
                # Skip all descriptors that are NOT in the `relations` list
                if name not in relations_:
                    warnings.warn(
                        f"Skipping => {name}, not in `relations` : {relations}"
                    )
                    continue
                value = getattr(entity, name, None)
                if value is None:
                    continue
                elif isinstance(value, Model) and options(value, "version", False):
                    if value in visited:
                        continue
                    else:
                        visited.add(value)
                        batch = BatchSet.objects.where(
                            entity=value, journal=diff.journal
                        ).get()
                        change = batch.change
                        if change is not None:
                            ops = self._revert_(
                                entity=value,
                                diff=change,
                                desc=desc,
                                visited=visited,
                                commit=False,
                                relations=relations,
                                ignore=ignore,
                            )
                            operations.append(ops)
                elif isinstance(value, Container):
                    kind = descriptor.type
                    if issubclass(kind, Model) and options(kind, "version", False):
                        warnings.warn(
                            "Expensive Op: Reverting Entire Collection Object Graph"
                        )
                        for var in value:
                            if var in visited:
                                continue
                            else:
                                visited.add(var)
                                batch = BatchSet.objects.where(
                                    entity=var, journal=diff.journal
                                ).get()
                                change = batch.change
                                if change is not None:
                                    ops = self._revert_(
                                        entity=var,
                                        diff=change,
                                        desc=desc,
                                        visited=visited,
                                        commit=False,
                                        relations=relations,
                                        ignore=ignore,
                                    )
                                    operations.append(ops)

        if commit:
            self.table._persist_(entity, operations, change=Edit.REVERT)
        else:
            return operations

    def _rollback_(self, entity: Model, diff: ChangeSet, ignore: List[str] = []):
        """Revert all changes to the host entity"""
        columns = set(diff.columns)
        properties = fields(entity, CqlProperty)
        for name in columns:
            if name not in properties and name not in ignore:
                raise RevisionError(
                    "Your `Entity` has changed. Column => %s was not found in %s"
                    % (name, entity.__class__)
                )
        """
        Implementation Note
        ===================
        The entire premise of change revision by cqlalchemy is defined by the following formula

              `batch of (last state commit + replayed differ ops ) = expected state

        So, we open a new batch, over write the current row with the ChangeSet.previous, then stream 
        all the change operations from the unpickled tracker operations as updates, then commit the 
        batch to C*, which effectively reverts our object to the state at your batch.
        """
        queries = []
        query = "INSERT INTO {table} ({columns}) VALUES ({values}){ttl};"
        expire = entity.expire
        ttl = " USING TTL {expire}".format(expire=expire) if expire else ""

        """1. Start with the last differ `commit``, and overwrite the existing row in C* including collections"""
        columns, values = [], []
        for name, value in diff.previous.items():
            # Skip columns which are in the ignore list
            if name in ignore:
                continue
            property = self.properties.get(name)
            if not property.saveable():
                continue
            columns.append(name)
            value = property.convert(self.entity, value)
            values.append(value)
        query = query.format(
            keyspace=entity.keyspace(),
            table=entity.table(),
            columns=", ".join(columns),
            values=", ".join(values),
            ttl=ttl,
        )
        queries.add(query)
        """
        2. Then, we use un-pickled operation data to update state of the row so that we capture ttl,
        and conditional updates for both top level members and 2nd level collections (which allows
        change revision to work for Expando, Vector and Block)
        """
        operations = []
        for operation in diff.ops:
            # Skip columns which are in the ignore list
            if operation.name not in ignore:
                operations.append(operation)
        for name, ops in diff.trackables:
            for operation in ops:
                operations.append(operation)
        """3. Sort all the change operations by the time they occurred"""
        operations = sorted(operations, key=lambda op: op.timestamp)
        deletion = [
            Action.LDELETE,
            Action.ODELETE,
            Action.MDELETE,
        ]
        for operation in operations:
            if operation.code in deletion:
                query = self.table._delete_(self.entity, operation)
                queries.append(query)
            else:
                query = self.table._update_(self.entity, operation)
                queries.append(query)
        """4. Return all the revision queries"""
        return queries

    def _remove_(self, desc: str):
        """Remove the underlying host entity"""
        self.table.delete(self.entity, description=desc)

    def revert(self, to: ChangeSet, description: str = ""):
        """Revise our host entity to the state in @to"""
        if not description:
            description = "Reverted to state at #{batch} using ChangeSet #{id}"
            description = description.format(batch=to.journal, id=to.id)

        match to.edit:
            case (Edit.INSERT, Edit.UPDATE, Edit.UPSERT, Edit.REVERT):
                self._revert_(
                    entity=self.entity,
                    diff=to,
                    desc=description,
                    visited=set(),
                    commit=True,
                )
            case Edit.DELETE:
                self._remove_(desc=description)
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
from cqlalchemy import String, Expando, Model, Batch

Book = Table("Book", Expando)

class Profile(Model, version=True):
    name = String(index=True, required=True)
    gender = String(choices=('M', 'F',))


# Create v1.0 of the objects in a batch 

with Batch() as batch:                                                          
    person = Profile.create(name="Jordan Lopez", gender='M')           
    one = Book.create(name="The Great Gatsby", author="F. Scott Fitzgerald")
    two = Book.create(name="The Adventures of Huckleberry Finn", author="Mark Twain")
    three = Book.create(name="To Kill a Mockingbird", author="Harper Lee")


# Change the person, and save it to create a v2.0 of it

person.name = "Jennifer Watson"                                                 
person.gender = 'F'
person.save()

#  Rewind the to the last change before `timestamp`    
          
timestamp = arrow.now().shift(seconds=-60)
person.history.restore(to=timestamp)                    

#  Rewind all the changes in entities to state as of `batch`

History.rewind([person, one, two, three], batch=batch.guid)                      
```
"""


class History(object):
    """Allows you to modify the history of a group of related objects"""

    def __init__(self, entity: Model):
        self.entity = entity

    def at(self, timestamp):
        """Returns the latest change relative to @timestamp"""
        timestamp = arrow.get(timestamp)
        change = (
            ChangeSet.objects.where(entity=self.entity, created=LTE(timestamp))
            .limit(1)
            .execute(filter=True)
            .first()
        )
        if change:
            return ChangeSetProxy(change)
        else:
            return None

    def span(self, start, end):
        """Returns all the ChangeSet(s) between both points in time in history"""
        start, end = arrow.get(start), arrow.get(end)
        query = ChangeSet.objects.where(
            entity=self.entity, created=AND(GTE(start), LTE(end))
        ).execute(filter=True)
        for change in query.all():
            yield ChangeSetProxy(change)

    def latest(self):
        """Returns the most recent ChangeSet"""
        change = ChangeSet.objects.where(entity=self.entity).limit(1).first()
        if change:
            return ChangeSetProxy(change)
        else:
            return None

    def oldest(self):
        """Returns the oldest (or first) ChangeSet"""
        change = (
            ChangeSet.objects.where(entity=self.entity)
            .order("created", asc=True)
            .limit(1)
            .first()
        )
        if change:
            return ChangeSetProxy(change)
        else:
            return None

    def all(self, limit=100):
        """Returns all the ChangeSet(s) for the target entity"""
        query = (
            ChangeSet.objects.where(entity=self.entity)
            .limit(limit)
            .execute(filter=True)
        )
        for change in query.all():
            yield ChangeSetProxy(change)

    def restore(self, to: str, description: str = ""):
        """Restores the entity to state at timestamp @to or at batch @to"""
        try:
            stamp = arrow.get(to)
            change = self.at(timestamp=stamp)
        except Exception:
            batch = BatchSet.objects.where(entity=self.entity, journal=to).get()
            change = batch.change

        if change:
            change.revert(description=description)

    @classmethod
    def rewind(self, entities: List[Model], batch: str, description=""):
        """Rewind all the @entities to a shared @batch state in the past (in a new C* batch)"""

        with Batch() as batch:
            for entity in entities:
                batch = BatchSet.objects.where(entity=entity, journal=batch).get()
                if not batch:
                    continue
                else:
                    reverter = Reverter(entity)
                    reverter.revert(to=batch.change, description=description)


"""
prune

If you use change revision, your data store will grow to a large size very quickly. 
You can use `prune` to remove old revisions that you want to discard to reduce your disk usage. 

You can remove all change revisions up to timestamp `to` or all change revisions before 
batch `to`. We advise that you run prune on a different/dedicated thread, and preferably at a time when your 
cluster is not under heavy load.

C* Note
=======
Please note that you have to run compaction on C* to remove all the tombstones, in order to really 
remove the deleted data from disk; 
"""


def prune(to: str):
    """Deletes all ChangeSet objects before timestamp @to or before batch @to"""
    warnings.warn("Caution: This action will cause irreversible data loss.")
    warnings.warn("Expensive Op: Please run in a dedicated thread.")
    try:
        created = arrow.get(to)
        created = created.isoformat()
    except Exception:
        first = BatchSet.objects.where(journal=to).get()
        created = first.created.isoformat()
    query = "DELETE FROM {table} WHERE created <='{created}'"
    query = query.format(table=ChangeSet.table(), created=created)
    return execute(query, keyspace(), idempotent=True)
