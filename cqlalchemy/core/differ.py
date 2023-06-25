
"""Explicit Change Data Capture for Objects"""

import copy
from enum import Enum
from collections import OrderedDict
from dataclasses import dataclass

from cqlalchemy.connection.functions import Predicate

OpCode = Enum("Operation", [
    "SADD", "SDELETE",
    "OSET", "ODELETE", "OCHANGE", 
    "MADD", "MDELETE", 
    "LINSERT", "LAPPEND", "LPREPEND", "LDELETE",
])
  

@dataclass
class Operation(object):
    """Encapsulates an Operation which can occur on Trackable objects"""
    code : OpCode
    descriptor : object
    parent : object
    name : str
    key : object
    value : object
    index : int
    ttl : int
    predicate : Predicate

    def conditions(self, predicate: Predicate=None, ttl:int=0):
        """Attach extra persistence considerations to this Operation"""
        from cqlalchemy.core.models import Entity
        self.ttl = ttl 
        if predicate and isinstance(self.parent, Entity):
            self.predicate = predicate 
            predicate.entity = self.parent


class Trackable(object):
    """Abstract base for objects that track the changes that happen to them."""
    
    @classmethod
    def op(cls, code=None, parent=None, name=None, key=None, index=None, value=None):
        return Operation(
            code=code, descriptor=None, 
            parent=parent, name=name, key=key, 
            value=value, index=index,
            ttl=None, predicate=None
        )
    
    def changes(self):
        """Returns an ordered iterable stream of all the changes that have happened since the last commit"""
        raise NotImplementedError("Implemented in a subclass")

    def track(self, operation):
        """Record an operation into the Trackable objects change registry"""
        raise NotImplementedError("Implemented in a subclass")
    
    def commit(self):
        """Persist the changes in the Trackable, and discard them"""
        raise NotImplementedError("Implemented in a subclass")


class TrackableMixin(Trackable):
    """Mixin for objects that track the changes that happen to them."""
    
    def changes(self):
        """Returns an ordered iterable stream of all the changes that have happened since the last commit"""
        for operation in self.__tracker__.changes():
            yield operation

    def track(self, operation):
        """Record an operation into the Trackable objects change registry"""
        self.__tracker__.track(operation)
    
    def commit(self):
        """Persist the changes in the Trackable, and discard them"""
        self.__tracker__.commit()


class EntityTracker(Trackable):
    """Tracks changes that happen to Entity objects"""

    def __init__(self, owner, exclude=[]):
        """Initializes the generic Tracker object"""
        from cqlalchemy.core.models import Entity, CqlProperty
        from cqlalchemy.core.builtins import fields
        
        if not isinstance(owner, Entity):
            raise ValueError("EntityTracker only works on Entity instances")
        if not hasattr(owner, "__store__"):
            raise ValueError("Trackable objects must have the __store__ attribute which tracks their state")
        
        self.owner = owner
        self.ops = OrderedDict()
        self.state = copy.deepcopy(owner.__store__)
        self.excluded = set(exclude)
        self.new = True
        self.properties = fields(self.owner, CqlProperty)

    def changes(self):
        """Returns an ordered iterable stream of all the changes that have happened since the last commit"""
        for name in self.ops:
            yield self.ops[name]
    
    def dirty(self):
        """Returns True if this object has changed since the last commit"""
        return self.state != self.owner.__store__

    def track(self, operation):
        """Record an operation into the Trackable objects' change registry"""
        if operation.name in self.excluded:
            return 
        if operation.code == OpCode.OSET:   # Track Updates for Objects
            previous = self.state.get(operation.name, None)
            if previous:
                if operation.value is None:
                    operation.code = OpCode.ODELETE
                elif operation.value != previous:
                    operation.code = OpCode.OCHANGE
            else:
                operation.code = OpCode.OSET
        self.ops[operation.name] = operation 
    
    def commit(self):
        """Persist the changes in the Trackable, and discard them"""
        stash = copy.deepcopy(self.owner.__store__)
        self.new = False 
        for name in self.properties:
            value = getattr(self.owner, name, None)
            if value and isinstance(value, Trackable):
                value.commit()
        self.ops.clear()
        self.state = stash

class CollectionTracker(Trackable):
    """Mirrors operations on a local List object for transmission to C*"""

    def __init__(self, owner):
        """Initializes the generic Tracker object"""
        from cqlalchemy.core.types import List, Set, Map

        if not isinstance(owner, (List, Set, Map)):
            raise ValueError("CollectionTracker only works on List<T>, Map<T,V> or Set<T> instances")
        
        self.owner = owner
        self.ops = []
        self.state = copy.deepcopy(owner)
        self.new = True

    def changes(self):
        """Returns an ordered iterable stream of all the changes that have happened since the last commit"""
        for operation in self.ops:
            yield operation
    
    def dirty(self):
        """Returns True if this object has changed since the last commit"""
        return self.state != self.owner

    def track(self, operation):
        """Record an operation into the Trackable objects' change registry"""
        self.ops.append(operation)
        
    def commit(self):
        """Persist the changes in the Trackable, and discard them"""
        self.state = copy.deepcopy(self.owner)
        self.ops.clear()
        self.new = False 

        

def changes(instance: Trackable):
    """Generates all the changes from a Trackable object, and its Trackable attributes"""
    from cqlalchemy.core.builtins import fields
    from cqlalchemy.core.models import CqlProperty, Entity

    if not trackable(instance):
        raise ValueError("You may only attempt to yield changes from a Trackable object")

    # Return all the changes in the parent object, and children
    if isinstance(instance, Entity):
        tracker = instance.__tracker__
        attributes = fields(instance.__class__, CqlProperty)
        for operation in tracker.changes():  # Enrich & Return First Level of Changes, 
            if operation.name in attributes:
                name = operation.name
                yield operation

                value = operation.value 
                if trackable(value):
                    for operation in changes(value):
                        operation.name = name  # Help operations discover the names of their attribute/descriptor within the Entity
                        yield operation
    else:
        for operation in instance.changes():
            yield operation


def added(trackable, screen=None):
    """Returns all the attributes that have been added to @trackable in the last session"""
    results = []
    for operation in changes(trackable):
        if screen:
            positive = screen(operation)
            if not positive:
                continue 
        if operation.code == OpCode.OSET:
            results.append(operation)
    return results


def changed(trackable):
    """Returns True if this Trackable object has changed since the last commit"""
    if hasattr(trackable, "__tracker__"):
        return trackable.__tracker__.dirty()
    elif isinstance(trackable, Trackable):
        return trackable.dirty()
    else:
        raise ValueError("You must provide a Trackable object, not %s" % trackable)


def commit(trackable):
    """Commits the changes in this @trackable and all its members"""
    if isinstance(trackable, Trackable):
        trackable.commit()
    elif hasattr(trackable, "__tracker__"):
        trackable.__tracker__.commit()
    else:
        raise ValueError("You must provide a Trackable object, not %s" % trackable)


def trackable(instance):
    """Returns True if @instance is Trackable"""
    if isinstance(instance, Trackable):
        return True
    elif hasattr(instance, "__tracker__"):
        return True
    else:
        return False