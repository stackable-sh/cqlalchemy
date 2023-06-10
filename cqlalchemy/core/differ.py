
"""Explicit Change Data Capture for Objects"""

import copy

from enum import Enum
from collections import OrderedDict
from dataclasses import dataclass

OpCode = Enum("Operation", ["INSERT", "APPEND", "PREPEND", "SET", "DELETE", "ADD", "DISCARD"])
     
@dataclass
class Operation(object):
    """Encapsulates an Operation which can occur on Trackable objects"""
    code : OpCode
    instance : object
    name : str
    value : str 
    index : int

class Trackable(object):
    """Abstract base for objects that track the changes that happen to them."""
    
    @classmethod
    def op(cls, code=None, instance=None, name=None, index=None, value=None):
        return Operation(code=code, instance=instance, name=name, value=value, index=index)
    
    def changes(self):
        """Returns an ordered iterable stream of all the changes that have happened since the last commit"""
        raise NotImplementedError("Implemented in a subclass")

    def changed(self):
        """Returns the set of index(s) or attributes that have changed"""
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
        for struct in self.__tracker__.changes():
            yield struct

    def changed(self):
        """Returns the set of index(s) or attributes that have changed"""
        return self.__tracker__.changed()
    
    def track(self, operation):
        """Record an operation into the Trackable objects change registry"""
        self.__tracker__.track(operation)
    
    def commit(self):
        """Persist the changes in the Trackable, and discard them"""
        self.__tracker__.commit()


class Tracker(Trackable):
    """Abstract base for objects that track the changes that happen to them."""

    def __init__(self, owner, exclude=[]):
        """Initializes the generic Tracker object"""
        if not hasattr(owner, "__store__"):
            raise ValueError("Tracker objects must have the __store__ attribute which tracks their state")
        self.owner = owner
        self.ops = OrderedDict()
        self.state = copy.deepcopy(owner.__store__)
        self.excluded = set(exclude)
        self.new = True

    def changes(self):
        """Returns an ordered iterable stream of all the changes that have happened since the last commit"""
        for name in self.ops:
            yield (name, self.ops[name])
    
    def changed(self):
        """Returns the set of index(s) or attributes that have changed"""
        return self.ops.keys()
    
    def dirty(self):
        """Returns True if this object has changed since the last commit"""
        return self.state != self.owner.__store__

    def track(self, operation):
        """Record an operation into the Trackable objects' change registry"""
        if hasattr(operation, "name"):
            name = operation.name
        elif hasattr(operation, "index"):
            name = operation.index
        else:
            name = hash(operation.value)
        if name not in self.excluded:
            self.ops[name] = operation 
    
    def commit(self):
        """Persist the changes in the Trackable, and discard them"""
        from cqlalchemy.core.builtins import fields
        from cqlalchemy.core.models import CqlProperty

        self.state = copy.deepcopy(self.owner.__store__)
        self.ops.clear()
        self.new = False 
        for name in fields(self.owner, CqlProperty):
            value = getattr(self.owner, name, None)
            if value and isinstance(value, Trackable):
                value.commit()
    
def changes(trackable):
    """Generates all the changes from a Trackable object, and its Trackable attributes"""
    from cqlalchemy.core.builtins import fields
    from cqlalchemy.core.models import CqlProperty

    parent = trackable if isinstance(trackable, Trackable) else trackable.__tracker__
    if not isinstance(trackable, Trackable):
        if hasattr(trackable, "__tracker__"):
            parent = trackable.__tracker__
        else:
            raise ValueError("You have to provide an object that implements the Trackable protocol")
    else:
        parent = trackable
    # Return all the changes in the parent object, and children
    attributes = fields(trackable.__class__, CqlProperty)
    for name, operation in parent.changes():
        yield name, operation, parent
    for name, property in attributes.items():
        child = getattr(parent, name, None)
        if child and isinstance(child, Trackable):
            for name, operation in property.changes():
                yield name, operation, child


def commit(trackable):
    """Sends a commit signal for this object to all its trackers"""
    if isinstance(trackable, Trackable):
        trackable.commit()
    elif hasattr(trackable, "__tracker__"):
        trackable.__tracker__.commit()
    else:
        raise ValueError("You must provide a Trackable object, not %s" % trackable)
