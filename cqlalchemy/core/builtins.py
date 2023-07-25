import sys
import gc
import datetime
import orjson
from typing import List
from collections import OrderedDict
from threading import local

__all__ = [
    "object",
    "fields",
    "assertType",
    "assertNonNull",
    "assertNotType",
    "Global",
    "Local",
]


"""
Global:
A singleton for storing threadsafe project wide objects.
"""


class Global(object):
    """A global holder object."""

    @classmethod
    def instance(cls):
        """Returns the single instance of this object"""
        if hasattr(cls, "__instance__"):
            return cls.__instance__
        cls.__instance__ = cls()
        return cls.__instance__


"""
Local:
A singleton object for storing thread-local objects which are unique for each Thread. 
"""


class Local(local):
    """A Thread Local holder for objects shared by each thread."""

    @classmethod
    def instance(cls):
        """Returns the global instance of this holder"""
        if hasattr(cls, "__instance__"):
            return cls.__instance__
        cls.__instance__ = cls()
        return cls.__instance__


class IllegalStateException(RuntimeError):
    """General Exception to signal internal state inconsistency"""

    pass


"""
object:
This extends the builtin 'object' type to add keyword constructors
"""


class object(object):
    """An object that adds an automatic keyword based constructor to any object"""

    def __init__(self, **keywords):
        """Automatic constructor"""
        for name, value in keywords.items():
            setattr(self, name, value)


"""
json
Compatibility wrapper around orjson to make the behaviour similar to json in the standard library
"""


class json(object):
    """Compatibility JSON serializer that uses orjson under the hood"""

    @classmethod
    def dumps(self, object):
        """Ports orjson.dumps to json.dumps"""
        var = orjson.dumps(object)
        return var.decode()

    @classmethod
    def loads(self, var):
        """Ports orjson.loads to json.loads"""
        var = var.encode()
        return orjson.loads(var)


def assertNonNull(object, error=None):
    """Checks that @object is non null"""
    if not error:
        error = "object must be non null"
    if object is None:
        raise ValueError(error)


def assertType(object, kind, error=None):
    """Checks that you passed in a particular class"""
    assertNonNull(object)
    assertNonNull(kind)
    object = object if isinstance(object, type) else object.__class__
    if not issubclass(object, kind):
        if not error:
            error = "%s must be a sub class of %s" % (object, kind)
        raise ValueError(error)


def assertNotType(object, kind, error=None):
    """Checks that you didn't pass in a particular class"""
    assertNonNull(object)
    assertNonNull(kind)
    object = object if isinstance(object, type) else object.__class__
    if issubclass(object, kind):
        if not error:
            error = "%s must be a sub class of %s" % (object, kind)
        raise ValueError(error)


def fields(cls, instance):
    """Searches a class heirachy for instances of a particular type"""
    if not isinstance(cls, type):
        cls = cls.__class__
    if not isinstance(instance, type):
        instance = instance.__class__
    results = OrderedDict()
    # Search the instance/class heirachy.
    for root in reversed(cls.__mro__):
        for name, prop in list(root.__dict__.items()):
            category = prop.__class__
            if issubclass(category, instance):
                results[name] = prop
    return results


def now():
    """Returns timestamp in milliseconds since Epoch from our local clock"""
    stamp = datetime.datetime.now()
    epoch = datetime.datetime(1970, 1, 1, tzinfo=stamp.tzinfo)
    offset = epoch.tzinfo.utcoffset(epoch).total_seconds() if epoch.tzinfo else 0
    return int(((stamp - epoch).total_seconds() - offset) * 1000)


def size(data: List):
    """Returns a better estimate of the size of a python object"""
    memory_size = 0
    ids = set()
    objects = []
    objects.extend(data)
    while objects:
        new = []
        for obj in objects:
            if id(obj) not in ids:
                ids.add(id(obj))
                memory_size += sys.getsizeof(obj)
                new.append(obj)
        objects = gc.get_referents(*new)
    return memory_size


def quote(value):
    """Makes a text value CQL safe by escaping it if necessary"""
    if isinstance(value, bytes):
        value = value.encode("utf_8")
        return "'%s'" % value
    elif isinstance(value, str):
        return "'%s'" % escape(str(value), "'", "''")
    else:
        return str(value)



def name(value):
    """Used to un-quote CQL names properly"""
    if isinstance(value, str):
        value = value.encode("utf_8")
    value = escape(value, "'", "")
    return value



def escape(term, char, replacement):
    if not isinstance(term, str):
        raise ValueError("We can only escape strings")
    return term.replace(char, replacement)

