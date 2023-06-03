from threading import local

__all__ = ["object", "fields", "assertType", "assertNonNull",  "assertNotType", "Global", "Local"]


"""
Global:
A singleton for storing threadsafe project wide objects.
"""
class Global(object):
    '''A global holder object.'''
    
    @classmethod
    def instance(cls):
        '''Returns the single instance of this object'''
        if hasattr(cls, "__instance__"):
            return cls.__instance__
        cls.__instance__ = cls()
        return cls.__instance__


"""
Local:
A singleton object for storing thread-local objects which are unique for each Thread. 
"""
class Local(local):
    '''A Thread Local holder for objects shared by each thread.'''
    
    @classmethod
    def instance(cls):
        '''Returns the global instance of this holder'''
        if hasattr(cls, "__instance__"):
            return cls.__instance__
        cls.__instance__ = cls()
        return cls.__instance__
    


"""
object:
This extends the builtin 'object' type to add keyword constructors
"""
class object(object):
    ''' An object that adds an automatic keyword based constructor to any object'''
    def __init__(self, **keywords):
        '''Automatic constructor'''
        for name, value in list(keywords.items()):
            setattr(self, name, value)



def assertNonNull(object, error=None):
    '''Checks that @object is non null'''
    if not error:
        error = "object must be non null"
    if object is None:
        raise ValueError(error)


def assertType(object, kind, error=None):
    '''Checks that you passed in a particular class'''
    assertNonNull(object)
    assertNonNull(kind)
    object = object if isinstance(object, type) else object.__class__
    if not issubclass(object, kind):
        if not error:
            error = "%s must be a sub class of %s" % (object, kind)
        raise ValueError(error)


def assertNotType(object, kind, error=None):
    '''Checks that you didn't pass in a particular class'''
    assertNonNull(object)
    assertNonNull(kind)
    object = object if isinstance(object, type) else object.__class__
    if issubclass(object, kind):
        if not error:
            error = "%s must be a sub class of %s" % (object, kind)
        raise ValueError(error)


def fields(cls, instance):
    '''Searches a class heirachy for instances of a particular type'''
    if not isinstance(cls, type): 
        cls = cls.__class__ 
    if not isinstance(instance, type): 
        instance = instance.__class__
    results = dict()
    # Search the instance/class heirachy.       
    for root in reversed(cls.__mro__):
        for name, prop in list(root.__dict__.items()):
            category = prop.__class__ 
            if issubclass(category, instance):
                results[name] = prop
    return results
