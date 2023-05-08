
import copy
import itertools

"""
Differ:
The differ module contains utilities that helps cqlalchemy to diff objects 
and retrieve properties that have changed. 
"""

class DiffError(Exception):
    """Represents any exception that gets thrown during diffing"""
    pass
    

class Differ(object):
    """A class that knows how to calculate changes in an object"""
    def __init__(self, instance, exclude):
        '''Inserts all the objects in @args to this differ'''

        if not hasattr(instance, "__store__"):
            raise ValueError("Differs only works on objects with the `__store__` attribute")
        
        self.excluded = exclude
        self.replica = copy.deepcopy(instance.__store__)
        self.model = instance.__store__
        self.instance = instance
    
    def forbidden(self, name):
        '''Excludes names in provided in self.excluded'''
        return name in self.excluded
    
    def update(self, name):
        '''Updates a single property in the differ, marking it as committed'''
        if not self.forbidden(name):
            value = self.model[name]
            self.replica[name] = value
            return True
        return False
              
    def added(self):
        '''Yields the names of the attributes that were recently added to this model'''
        # I used getattr(), because properties will return their default values or None by default
        dict = self.model
        for name in dict:
            if not self.replica.get(name, None):
                if not self.forbidden(name):
                    yield name
            
    def deleted(self):
        '''Yields the names of the attributes that were deleted from this model'''
        dict = self.replica
        for name in dict:
            if name not in self.model:
                if not self.forbidden(name):
                    yield name
    
    def modified(self):
        '''Return all the attributes that were modified in any way in this model'''
        dict = self.replica
        for name in dict:
            if name in self.model:
                if dict[name] != self.model[name]:
                    if not self.forbidden(name):
                        yield name
    
    def changed(self):
        '''Cummulative set of all the attributes that have been deleted|modified|added'''
        result = set()
        added = list(self.added())
        deleted = list(self.deleted())
        modified = list(self.modified())
        for i in itertools.chain(added, deleted, modified):
            result.add(i)
        return result
        
    def commit(self):
        '''Make the current state the default state for this Differ'''
        self.replica = copy.deepcopy(self.instance.__store__)
   
    def revert(self):
        '''Reverts @self.model to the previous commit state'''
        # This method will be used to implement a rollback feature for Models
        clean = self.replica
        dirty = self.model
        dispose = [v for v in dirty if v not in clean]
        # Revert all known attributes
        for name in clean:
            setattr(self.instance, name, clean[name])
        # Delete all new attributes
        for name in dispose: 
            delattr(self.model, name)
        self.commit()
   
    
    
    
    
