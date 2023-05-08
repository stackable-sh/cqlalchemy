
import re
import uuid
import json 
import struct
import base64
import socket
import itertools
import ipaddress
import pickle as pickle

from uuid import UUID
import datetime
import urllib.parse
import traceback

import arrow
from .serialization import Size, quote
from .builtins import assertType
from .types import phone, blob, Map, Set, List
from .models import Model, READWRITE, READONLY, Basic, Type, BadValueError
from .models import CqlCollection, CqlProperty, Reference

MAX = 1024 * 1024 * 1 #1MB

__all__ = [ 
    "Integer", "Long", "String", "Name", "Blob", "Boolean", "URL", "Time", "DateTime",
    "Phone", "Pickle", "Date", "Float", "Double", "Map", "Set", "List", "IPAddress"
]

"""
Phone:
A descriptor that stores phone objects,
"""
class Phone(Basic):
    '''An descriptor that contains phone objects'''
    type, ctype = phone, "text"
    
    def convert(self, instance=None, value=None):
        '''Yields the datastore representation of its value'''
        value = self.validate(value)
        return repr(value)
    
    def deconvert(self, value):
        '''Converts a value from the datastore to a native python object'''
        if not isinstance(value, str): raise BadValueError("Phone: requires a base string")
        result = eval(value)
        if not isinstance(result, phone):
            raise BadValueError("Got unexpected type after serialization")
        return result
              
"""
Float:
A data descriptor for modeling Floats in your 'things'. It coerces like the normal
python float

# ... snippet ...
class Circle(object):
    pi = Float()
    
"""
class Float(Basic):
    """ A float descriptor """
    type, ctype = float, "float"
    
    def deconvert(self, value):
        '''Converts the stream of bytes from cassandra to a valid float.'''
        found = struct.unpack(">f", value)[0]
        return found

"""
Double:
A data descriptor for modeling Doubles in your 'things'. 
It coerces like the normal python float

# ... snippet ...
class Circle(object):
    pi = Double()
    
"""
class Double(Basic):
    """ A float descriptor """
    type, ctype = float, "double"
    
    def deconvert(self, value):
        '''Converts the stream of bytes from cassandra to a valid float.'''
        found = struct.unpack(">d", value)[0]
        return found
        
    
"""
Integer:
A data descriptor that is used to create properties for  ints in 
your models. All integers are represented as 32bit signed integers within. 
Integers behavelike normal python ints and they coerce values.

# .. snippet ...
class Balls(object)
    number = Integer(choices=range(1,5))
    sold = Integer()
    
"""
class Integer(Basic):
    """Data descriptor for an Integer"""
    type, ctype = int, "int"
    
    def deconvert(self, value):
        '''Converts a stream of bytes from cassandra to valid integer'''
        found = struct.unpack(">i", value)[0]
        return found

"""
Long:
A data descriptor that is used to create properties for longs in 
your models. All integers are represented as 64bit signed longs within. 
Longs behave like normal python longs and they coerce values.

# .. snippet ...
class Balls(object)
    number = Long(choices=range(1,5))
    sold = Long()
    
"""
class Long(Basic):
    """Data descriptor for an Integer"""
    type, ctype = int, "bigint"
    
    def deconvert(self, value):
        '''Converts a stream of bytes from cassandra to valid integer'''
        found = struct.unpack(">q", value)[0]
        return found

"""
Boolean:
A descriptor that coerces any value set to it to a boolean. it behaves like 
the python bool builtin function. Boolean uses pythonic truth. so beware!!!.
e.g.
class Person(object):
    married = Boolean()

person = Person()
person.married = "Married"
assert person.married == True
person.married = True
assert person.married == True

"""        
class Boolean(Basic):
    """Stores Boolean values, It coerces values like normal python bools"""
    type, ctype = bool, "boolean"
    
    
    def deconvert(self, value):
        '''Converts @value to a suitable python representation.'''
        if value is None: return False
        found = struct.unpack(">b", value)[0]
        return bool(found)
    
 
"""
String:
This descriptor allows you to store unicode safe text in Apache Cassandra. The following snippet shows various 
usecases for string; 

class Story(object):
    channel = String("BBC World News", pattern=r'COUNT\(.+\)')
    reporter = String(length 30)
"""
class String(Basic):
    """A data descriptor that wraps Strings"""
    type, ctype = str, "text"
    
    def __init__(self, **arguments):
        """ Construct property """
        length = arguments.pop("length", 8192)
        pattern = arguments.pop("pattern", None)
        if length <= 0:
            raise ValueError("Length must be greater than zero")
        self.length = length
        if pattern:
            self.pattern = re.compile(pattern)
        else:
            self.pattern = None
        super(String,self).__init__(**arguments)
   
    def validate(self, value):
        """Validate length here"""
        value = super(String,self).validate(value)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf_8", "strict")
        if not isinstance(value, str):
            value = str(value, encoding="utf_8")
        if not len(value) <= self.length:
            raise BadValueError("Too long. Expected : %s , Got : %s" % (self.length, len(value)))
        if self.pattern and not self.pattern.match(value):
            raise BadValueError("Value doesn't match pattern: %s" % self.pattern)
        return value
    
    def deconvert(self, value):
        '''Simply returns the value passed in from the data store'''
        return value

"""
IPAddress:
Validates and Stores IP Addresses (both V4 & V6) in Cassandra
"""
class IPAddress(Basic):
    type, ctype = str, "inet"
    
    def __init__(self, **keywords):
        '''initializes the IP Address'''
        super(IPAddress, self).__init__(**keywords)
        
    def validate(self, value):
        '''Checks that you have set a valid IP address'''
        value = super(IPAddress, self).validate(value)
        try:
            ipaddress.ip_address(value)
            return value
        except Exception as e:
            raise BadValueError("Got invalid IP Address: %s" % str(value))
    
    def deconvert(self, value):
        '''Converts a value from the datastore repr to a native python object'''
        if len(value) == 16:
            fam = socket.AF_INET6
        else:
            fam = socket.AF_INET
        return socket.inet_ntop(fam, value)

"""
Pickle:
This descriptor allows you to automatically pickle and store
python objects in Apache Cassandra. 

class NewsPaper(Model):
    headlines = Pickle()
"""
class Pickle(Basic):
    """Pickles and stores python objects in Cassandra"""
    
    def __init__(self, **keywords):
        '''Initializes the pickle descriptor'''
        super(Pickle, self).__init__(**keywords)
    
    def convert(self, instance=None, value=None):
        '''Defines insert behavior for basic python types'''
        value = pickle.dumps(value)
        return quote(value)
        
    def validate(self, value):
        """Pickle can store almost any python object, including None."""
        return value
    
    def deconvert(self, value):
        '''Simply returns the value passed in from the data store'''
        if isinstance(value, str):
            return pickle.loads(value)
        elif value is None:
            return None
        else:
            raise BadValueError("Pickle can only load string")

"""
Name:
This descriptor is the same as String, the only difference is that it 
only allows you to store case-insensitive alpha numeric values with or 
without underscores - although values cannot start with underscores. 

This property was designed to allow you to store values that can be 
used as Apache Cassandra column names safely.

class Story(object):
    '''Models a Story Object'''
    channel = Name("BBC_World_News", pattern=r'COUNT\(.+\)')
"""
class Name(String):
    """A data descriptor that wraps Strings"""
    
    def __init__(self, **keywords):
        """ Construct property """
        super(Name,self).__init__(**keywords)
   
    def validate(self, value):
        """Validate length here"""
        value = super(Name, self).validate(value)
        if value:
            value = value.lower()
            if value.startswith("_"):
                raise BadValueError("This Property doesn't allow values starting with an underscore")
            for c in value:
                valid = bool(c.isalpha() or c == "_")
                if not valid:
                    raise BadValueError("Value: %s contains an invalid character" % value)
            return value
        else:
            raise BadValueError("You must put a valid alpha numeric string here.")
           
"""
Blob:
Blob is a data descriptor for storing blobs in cassandra, it provides 
useful features like size monitoring for data you put within it. If you set 
its size parameter to "-1" then this blob can store elements of any size.
Internally, we encode this blob into a JSON object which contains a 
Base64 encoded version of the data, along with metadata for the data
which you set on it.


class Person(object):
    '''A simple person model'''
    headshot = Blob(size=1024*50)

....
"""   
class Blob(Basic):
    """Store Blobs as Text in Cassandra"""
    ctype = "text"
    
    def __init__(self, default="", size=MAX, **arguments):
        '''Creates a Blob descriptor'''
        if "choices" in arguments: 
            raise BadValueError("Choices do not mean anything in Blobs")
        self.__size = size
        super(Blob,self).__init__(default=default,**arguments)
    
    def __get__(self, instance, owner):
        '''Returns returns the blob.'''
        blob = super(Blob, self).__get__(instance, owner)
        return blob.content
        
    def indexed(self):
        '''Blobs cannot be indexed'''
        return False;
             
    @property
    def size(self):
        """Whatever you store in this Blob MUST not be larger than the size property"""
        return self.__size
    
    def validate(self, value):
        """Makes sure that whatever you are putting, does not exceed size"""
        inBytes = Size.inBytes(value)
        if not inBytes <= self.size and not self.size <= -1:
            raise BadValueError("Your blob size must be less than: %s , got: %s" % self.size, inBytes)
        if not isinstance(value, blob):
            if isinstance(value, str):
                value = blob(value)
            else:
                value = blob(str(value))
        return value
    
    def convert(self, instance=None, value=None):
        '''Converts a Blob to its appropriate representation'''
        value = self.validate(value)
        return super(Blob, self).convert(instance, value)
        
    def deconvert(self, value):
        '''Change a JSON repr of a blob stored in the datastore to a python object'''
        loaded = json.loads(value)
        content = base64.b64decode(loaded["content"])
        new = blob(
            content=content, mimetype=loaded["mimetype"],
            **loaded["metadata"]
        )
        return new                             
        
"""
URL:
A URL descriptor that validates strings to make sure they are valid URLs.
It inherits String, so you can use it like a string.It uses a Strings default
length of 500 chars, If you need a longer URL, modify its length property.
e.g.

class Person(object):
    website = URL(default="http://harem.tumblr.com")
       
"""        
class URL(String):
    """Makes sure that a string you are creating is a valid URL"""
    length = 1024 # We cannot store URL's longer than 1024 characters.
    
    def empty(self, value):
        '''What does it mean for a URL to be empty'''
        return value is None or not bool(value.strip())
        
    def validate(self,value):
        """Uses urlsplit to validate urls"""
        value = super(URL, self).validate(value)
        if value is not None and value.strip():
            parsed = urllib.parse.urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise BadValueError('Property %s must be a full URL (\'%s\')' %
                    (self.name, value))
        return value

"""
DateTime:
A descriptor that stores a datetime. It implements autonow keyword which makes sure
that the the attribute always return the current value from the datetime module
...
class Person(object):
    birthdate = DateTime()
    modified = DateTime(autonow=True)
"""
class DateTime(Type):
    """Base class of all date time properties"""
    type, ctype = datetime.datetime, "text"
    
    def __init__(self, **arguments):
        self.autonow = arguments.pop("autonow", False)
        super(DateTime,self).__init__(**arguments)
    
    def __get__(self, instance, owner):
        """Overrides get to implement autonow"""
        if self.autonow:
            now = self.now()
            self.__set__(instance, now)
        return super(DateTime,self).__get__(instance,owner)
    
    def validate(self, value):
        """Add type checking and coercion and automatic construction to basic validation"""
        if not isinstance(value, self.type):
            raise BadValueError("We only accept datetime objects here")
        return value
    
    def convert(self, instance=None, value=None):
        '''Yields the datastore representation of its value'''
        value = self.validate(value)
        value = quote(value.isoformat())
        return value
    
    def deconvert(self, value):
        '''Converts a value from the datastore to a native python object'''
        if value is None: 
            return None
        try:
            value = arrow.get(value).datetime()
            return value
        except Exception as e:
            raise BadValueError("Expected an ISO 8601 DateTime string from deconversion")
    
    def serialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, datetime.datetime):
            raise BadValueError("You cannot serialize a non datetime object with this serializer")
        return value.isoformat()
    
    def deserialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, str):
            raise BadValueError("We expect an ISO formatted string here")
        val = arrow.get(value).datetime()
        return val
        
    def __insert__(self, instance=None, value=None):
        '''Yields the datastore representation of its value'''
        return self.convert(instance, value)
    
    def __update__(self, instance=None, value=None):
        '''Yields the datastore representation of its value'''
        assertType(instance, Model)
        value = self.convert(instance, value)
        return "%s = %s" % (self.name, value)
    
    def empty(self, value):
        '''DateTime's are empty when they are none'''
        return value is None
        
    def now(self):
        """Helper to return a datetime representing now"""
        return datetime.datetime.now()
    
         
"""
Time:
Descriptor for storing Times, It stores the time part of a datetime.
sample usage:

    class BreakingNews(object):
        headline = Story()
        time = Time()
"""
class Time(DateTime):
    """Stores only the time part of a datetime"""
    type, ctype = datetime.time, "text"
    
    def now(self):
        return datetime.datetime.now().time()
    
    def validate(self, value):
        """Add type checking and coercion and automatic construction to basic validation"""
        value = super(Time, self).validate(value)
        if not isinstance(value, self.type):
            raise BadValueError("We only accept datetime objects here")
        return value
    
    def convert(self, instance=None, value=None):
        '''Yields the datastore representation of its value'''
        value = self.validate(value)
        value = quote(value.isoformat())
        return value
    
    def deconvert(self, value):
        '''Converts a value from the datastore to a native python object'''
        if value is None: return None
        try:
            value = maya.parse(value).datetime().time()
            return value
        except Exception as e:
            traceback.print_exc(e)
            raise BadValueError("Expected an ISO 8601 DateTime string from deconversion")
    
    def serialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, self.type):
            raise BadValueError("You cannot serialize a non datetime object with this serializer")
        val = maya.parse(value).datetime().time()
        return val.isoformat()
    
    def deserialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, str):
            raise BadValueError("We expect an ISO 8601 formatted datetime string here")
        val = maya.parse(value).datetime().time()
        return val

"""
Date:
Descriptor for storing Dates, It stores the date part of a datetime
e.g.

class BreakingNews(object):
    headline = Story()
    time = Date()
"""
class Date(DateTime):
    """Stores the Date part of a datetime"""
    type, ctype = datetime.date, "text"
    
    def now(self):
        return datetime.datetime.now().date()
    
    def validate(self, value):
        """Add type checking and coercion and automatic construction to basic validation"""
        value = super(Date, self).validate(value)
        if not isinstance(value, self.type):
            raise BadValueError("We only accept datetime objects here")
        return value
        
    def convert(self, instance=None, value=None):
        '''Yields the datastore representation of its value'''
        value = self.validate(value)
        value = quote(value.isoformat())
        return value
    
    def deconvert(self, value):
        '''Converts a value from the datastore to a native python object'''
        if value is None: return None
        try:
            value = maya.parse(value).datetime().date()
            return value
        except Exception as e:
            raise BadValueError("Expected an ISO 8601 DateTime string from deconversion")
    
    def serialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, self.type):
            raise BadValueError("You cannot serialize a non datetime object with this serializer")
        return value.isoformat()
    
    def deserialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, str):
            raise BadValueError("We expect an ISO 8601 formatted datetime string here")
        val = maya.parse(value).datetime().date()
        return val
        
"""
List:
A descriptor that stores homogeneous lists. List works like the Set 
descriptor except that Lists can accept duplicates. by default it is 
an empty list.

    class Person(object):
        name = String()
        harem = List(String)

    person = Person()
    person.harem.extend(["Aisha","Halima","Safia",])
"""
class List(CqlCollection):
    """Stores a List of objects,You can specify the type of the objects this list contains"""
    
    def __init__(self, T, **keywords): 
        '''Stores a List of objects in Cassandra'''
        if not issubclass(T, (CqlProperty, Model)): raise BadValueError("T: {0} must be a CqlProperty or Model".format(T))
        if issubclass(T, Model):
            self.converter = Reference(T)
        else : self.converter = T()
        self.type = T
        super(List, self).__init__(**keywords)
    
    @property
    def ctype(self):
        '''A property that generates the ctype of its set dynamically'''
        fragment = "list<{type}>"
        return fragment.format(type=self.converter.ctype)
    
    def deconvert(self, value):
        '''Changes the binary repr to a python list'''
        if value is None: return None
        unpack = lambda s: struct.unpack('>H', s)[0]
        size = unpack(value[:2])
        p = 2
        result = []
        for n in range(size):
            length = unpack(value[p:p+2])
            p += 2
            item = value[p:p+length]
            p += length
            result.append(self.converter.deconvert(value=item))
        created = TypedList(T=self.type, data=result)
        created.commit()
        return created
    
    def _escape_(self, iterable):
        '''Useful for changing a list to it appropriate CQL3 representation'''
        return '[' + ', '.join(iterable) + ']'
    
    def convert(self, instance=None, value=None):
        '''Convert to a suitable CQL representation'''
        assertType(instance, Model)
        value = self.validate(value)
        property = self.converter
        converted = [property.convert(value=v) for v in value]
        return self._escape_(converted)
        
    def __insert__(self, instance=None, value=None):
        '''Converts data to queries'''
        return self.convert(instance, value)
    
    def __update__(self, instance=None, value=None):
        '''Converts data to queries'''
        assertType(instance, Model); assertType(value, TypedList);
        value = self.validate(value)
        property = self.converter
        if value.rewrite():
            converted = self.convert(instance, value)
            return "%s = %s" % (self.name, converted)
        else:
            changes = value.modifications() # Generate CQL assignments for appends and prepends
            prepend = [property.convert(value=value) for val in changes["prepend"]]
            before = "{name} = {value} + {name}".format(
                name = self.name,
                value = self._escape_(prepend)
            )
            append = [property.convert(value=value) for val in changes["append"]]
            after = "{name} = {name} + {value}".format(
                name = self.name,
                value = self._escape_(append)
            )
            return [before, after]   
    
    def validate(self, value):
        """Validates a list and all its contents"""
        if value is None: 
            return TypedList(self.type, [])
        if isinstance(value, TypedList):
            if isinstance(value.type, self.type):
                return value
        if not isinstance(value, list):
            try: value = list(value)
            except Exception as e:
                raise BadValueError("Could not coerce %s to a list due to: %s" % (type(value), str(e)))
        created = TypedList(T=self.type, data=value)
        return created 
    
"""
Set:
A descriptor that describes homogenuous python sets which
you can be stored directly in cassandra.
...
class Person(object):
    spouses = Set(User)

"""
class Set(CqlCollection):
    """A data descriptor for storing sets"""
    def __init__(self, T, **keywords):
        assertType(T, (CqlProperty, Model), "T: {0} must be a CqlProperty or Model".format(T))
        if issubclass(T, Model):
            self.converter = Reference(T)
        else : self.converter = T()
        self.type = T
        super(Set, self).__init__(**keywords)
    
    @property
    def ctype(self):
        '''A property that generates the ctype of its set dynamically'''
        fragment = "set<{type}>"
        return fragment.format(type=self.converter.ctype)
    
    def deconvert(self, value):
        '''Converts the set to python'''
        if value is None: return None
        unpack = lambda s: struct.unpack('>H', s)[0]
        size = unpack(value[:2])
        p = 2
        result = set()
        for n in range(size):
            length = unpack(value[p:p+2])
            p += 2
            item = value[p:p+length]
            p += length
            result.add(self.converter.deconvert(value=item))
        created = TypedSet(T=self.type, data=result)
        return created
        
    def _escape_(self, iterable):
        '''Useful for changing a set to it appropriate CQL3 representation'''
        return '{' + ', '.join(iterable) + '}'
        
    def convert(self, instance=None, value=None):
        '''Generates the CQL query for a particular set object'''
        assertType(instance, Model)
        value = self.validate(value)
        property = self.converter
        converted = [property.convert(value=val) for val in value]
        return self._escape_(converted) # Just return the value directly.
        
    def __insert__(self, instance=None, value=None):
        '''Generates the CQL query for a particular set object'''
        return self.convert(instance, value)
    
    def __update__(self, instance=None, value=None, conditions=None):
        '''Generates the CQL query assignment for this set object'''
        assertType(instance, Model); assertType(value, TypedSet)
        value = self.validate(value)
        property = self.converter
        added = [property.convert(value=v) for v in value.added()]
        add = "{name} = {name} + {value}".format(
            name = self.name,
            value = self._escape_(added)
        )
        removed = [property.convert(value=v) for v in value.deleted()]
        remove = "{name} = {name} - {value}".format(
            name = self.name,
            value = self._escape_(removed)
        )
        result = [add, remove]
        return result
            
    def validate(self,value):
        """Validates the type you are setting and its contents"""
        if value is None: 
            return TypedSet(self.type, [])
        if isinstance(value, TypedSet):
            if issubclass(value.type, self.type):
                return value
        if not isinstance(value, list):
            try: value = set(value)
            except Exception as e:
                raise BadValueError("Could not coerce %s to a set due to: %s" % (type(value), str(e)))
        created = TypedSet(T=self.type, data=value)
        return created
 

"""
Map:
A descriptor for dict-like objects with specific predefined
types in Cassandra;

class Person(object):
    bookmarks = Map(String, URL)
"""
class Map(CqlCollection):
    '''Map descriptor for dict objects.'''
    
    def __init__(self, K, V, **keywords):
        '''Map descriptor for dict objects.'''
        assertType(K, (CqlProperty, Model), "K must be a CqlProperty or a Model")
        assertType(V, (CqlProperty, Model), "V must be a CqlProperty")
        self.type = (K, V)
        K = Reference(K) if issubclass(K, Model) else K()
        V = Reference(V) if issubclass(V, Model) else V()
        self.converter = (K, V)
        super(Map, self).__init__(**keywords)
    
    @property
    def ctype(self):
        '''A property that generates the ctype of its set dynamically'''
        fragment = "map<{key},{value}>"
        k, v = self.converter
        return fragment.format(key=k.ctype, value=v.ctype)
    
    def _escape_(self, iterable):
        '''Converts this Map to its appropriate CQL3 representation'''
        return '{' + ', '.join([ key +':' + value for key, value in list(iterable.items())]) + '}'
        
    def convert(self, instance=None, value=None):
        '''Generates the CQL update and insert queries for Map descriptor'''
        value = self.validate(value)
        k, v = self.converter
        converted = {k.convert(value=key) : v.convert(value=value) for key, value in list(value.items())}
        return self._escape_(converted)
        
    def __insert__(self, instance=None, value=None):
        '''Generates the CQL update and insert queries for Map descriptor'''
        return self.convert(instance, value)
            
    def __update__(self, instance=None, value=None):
        '''Generates the CQL update and delete assignments for a Map descriptor'''
        assertType(value, TypedMap); assertType(instance, Model);
        value = self.validate(value)
        k, v = self.converter
        # HANDLE ADDITIONS & MODIFICATIONS
        updates = {
            "updates" : [],
            "deletes" : []
        }
        assignment = "{name}[{key}] = {value}"
        for name in itertools.chain(value.added(), value.modified()):
            a, b = name, value[name]
            q = assignment.format(
                name=self.name, 
                key=k.convert(value=a), 
                value=v.convert(value=b)
            )
            updates["updates"].append(q)
            
        deletes = "{name}[{key}]" # HANDLE DELETIONS
        for name in value.deleted():
            q = deletes.format(
                name = self.name,
                key = k.convert(value=name)
            )
            updates["deletes"].append(q)
        return updates
    
    def deconvert(self, value):
        '''Changes the Cassandra generated results to python'''
        if value is None: return None
        k, v = self.converter
        unpack = lambda s: struct.unpack('>H', s)[0]
        size = unpack(value[:2])
        p = 2
        dict = {}
        for n in range(size):
            keylen = unpack(value[p:p+2])
            p += 2
            keybytes = value[p:p+keylen]
            p += keylen
            vallen = unpack(value[p:p+2])
            p += 2
            valbytes = value[p:p+vallen]
            p += vallen
            key = k.deconvert(value=keybytes)
            val = v.deconvert(value=valbytes)
            dict[key] = val
        return dict
        
    def validate(self, map):
        '''Simply does type checking'''
        if map is None: 
            k, v = self.type
            return TypedMap(k, v, {})
        if isinstance(map, TypedMap):
            k, v = self.type; K, V = map.type
            if k == K and v == V:
                return map
            else: 
                raise BadValueError("You cannot set a TypedMap with a different signature on this descriptor")
        if not isinstance(map, dict):
            try: map = dict(map)
            except Exception as e:
                raise BadValueError("Could not coerce %s to a dictionary due to: %s" % (type(map), str(e)))
        if not isinstance(map, dict): raise BadValueError("Expected a dict, got: %s" % type(map))
        k, v = self.type
        coerced = TypedMap(K=k, V=v, data=map)
        return coerced
    

        

