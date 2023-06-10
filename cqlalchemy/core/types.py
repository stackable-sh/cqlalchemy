
import re
import sys
import ujson as json
import copy
import base64
import hashlib
from collections.abc import MutableMapping, MutableSet, MutableSequence

from .differ import TrackableMixin, Tracker, OpCode
from .models import Converter, Reference, Model, Collection

__all__ = ["phone", "blob", "Map", "Set", "List",]

MAX_BYTES_SIZE = 65535
MAX_LENGTH_COLLECTION = 65535

class ContainerException(Exception):
    '''Container Related Exceptions'''
    pass

class Container(object):
    """Base for all Container Type objects"""
    pass 

def __size__(*values):
    '''Checks that all the elements in value obey CQL size limits'''
    for value in values:
        if sys.getsizeof(value) > MAX_BYTES_SIZE:
            raise ContainerException("Value: %s size in bytes cannot fit into Apache Cassandra" % str(value))

def __length__(value):
    '''Checks that len(value) are within CQL length limits'''
    if len(value) > MAX_LENGTH_COLLECTION:
        raise ContainerException("Value: %s length cannot fit into Apache Cassandra" % str(value))

class phone(object):
    '''An immutable Phone number in international format'''
    pattern = re.compile("^\+(?:[0-9] ?){6,14}[0-9]$")

    def __init__(self, number):
        '''Simply pass in the number as one block. '''
        if not isinstance(number, str): raise ValueError("Type Error, Please use strings instead")
        number = number.strip()
        if not self.pattern.match(number):
            raise ValueError("Invalid international phone number")
        self.__number = number
    
    @property
    def number(self):
        '''A readonly property that returns the number part of this phone number'''
        return self.__number
    
    def __eq__(self, other):
        '''Equality tests'''
        if not isinstance(other, phone): raise ValueError("%s must be a phone type" % other)
        return self.number == other.number
         
    def __str__(self):
        '''String representation of an international phone number'''
        return self.number
    
    def __repr__(self):
        '''Returns a phone object as a tuple'''
        return "phone('%s')" % (self.number)


class blob(object):
    '''A opaque binary object with a content-type and description'''
    def __init__(self, content="", mimetype="application/text", **keywords):
        '''Basic constructor for a blob'''
        self.metadata = {}
        self.content = content
        self.mimetype = mimetype
        self.metadata.update(keywords)
        self.checksum = self._checksum_(content)
        
    def _checksum_(self, content):
        '''Calculates the md5 hash of the content and returns it as a string'''
        hasher = hashlib.md5()
        hasher.update(content.encode("utf_8"))
        return hasher.hexdigest()
            
    def __eq__(self, other):
        '''Compares the checksums if @other is a blob, else it compares content directly''' 
        if isinstance(other, blob):
            return self.checksum == other.checksum
        else: 
            return self.content == other
    
    def __sizeof__(self):
        '''Returns the size of this blob, this returns the size of the content string'''
        return sys.getsizeof(self.content)
        
    def __repr__(self):
        '''Returns a JSON representation of the contents of this blob'''
        template = 'blob(content="{content}", mimetype="{mimetype}", **{metadata})'
        return template.format(content=self.content, mimetype=self.mimetype, metadata=self.metadata)
    
    def __json__(self):
        '''Returns a JSON representation of this blob'''   
        dump = dict()
        dump['metadata'] = self.metadata
        dump['content'] = base64.b64encode(self.content)
        dump['mimetype'] = self.mimetype
        return json.dumps(dump)
        
    def __str__(self): 
        '''Returns a human readable string representation of the blob'''
        return "Blob: [mimetype:%s, checksum:%s]" % \
            (self.mimetype, self.checksum,)

"""
Map<K, V>

A mutable hash table that does type, size & length validation before storing items, 
and tracks changes to itself for persistence to C*, otherwise behaves like an ordinary python dict. 

```python
table = Map(String, Integer)
table['count'] = 1

# Create a Map container without validation

var = Map() 
table['count'] = "0"

```
"""
class Map(Container, MutableMapping, TrackableMixin):
    '''A map that does validation of keys and values'''

    def __init__(self, K=Converter, V=Converter):
        '''Initialization routine for Map<K, V>'''
        if not isinstance(K, type): raise ValueError("K must be a class")
        if isinstance(K, Collection): raise ValueError("You cannot put a Collection in a Map")
        if isinstance(K, Container): raise ValueError("You cannot put a Container in a Container")
        if not issubclass(K, (Converter, Model)): raise ValueError("T must be a Converter")
        
        if not isinstance(V, type): raise ValueError("V must be a class")
        if isinstance(V, Collection): raise ValueError("You cannot put a Collection in a Map")
        if isinstance(V, Container): raise ValueError("You cannot put a Container in a Container :)")
        if not issubclass(V, (Converter, Model)): raise ValueError("V must be a Converter")
        
        self.type = (K, V)
        self.K = Reference(K) if issubclass(K, Model) else K()
        self.V = Reference(V) if issubclass(V, Model) else V()
        self.__store__ = {}
        self.__tracker__ = Tracker(self)
    
    def __setitem__(self, key, value):
        '''Validate and possibly transform key, value before storage'''
        __size__(key, value)
        __length__(self)
        key, value = self.K(key), self.V(value)
        self.__store__[key] = value
        # Track the change explicitly if the __setitem__ didn't fail.
        operation = self.__tracker__.op(code=OpCode.SET, instance=self, name=key, value=value)
        self.__tracker__.track(operation)
    
    def __delitem__(self, key):
        '''Validate and possibly transform key before deletion'''
        key = self.K(key)
        del self.__store__[key]
        # Track the change explicitly if the __delitem__ didn't fail.
        operation = self.__tracker__.op(code=OpCode.DELETE, instance=self, name=key)
        self.__tracker__.track(operation)
        
    def __getitem__(self, key):
        '''Validate and possibly transform key before retreival'''
        key = self.K(key)
        value = self.__store__[key]
        return value

    def __iter__(self):
        '''Returns a iterable over the data set'''
        # If we have References with Models in them, read the Models and return them.
        for k in self.__store__:
            yield k
    
    def __str__(self):
        '''String representation of an object'''
        return str(self.__store__)

    def __eq__(self, other):
        if isinstance(other, Map):
            return self.__store__ == other.__data__
        elif isinstance(other, dict):
            return self.__store__ == other
        else:
            return False

    def __len__(self):
        '''Returns the number of the keys in this map'''
        return len(self.__store__)


"""
List<T>:

A mutable sequence that performs validation before storage.

By default it behaves like an ordinary list. If the data type (the `cls` attribute) of a List is 
a saved Model, the List stores the Model as `Key` object instead of pickling the model. 


```python
from cql.core.commons import String

friends = List(String)
friends.append("Hello")

# This does not do any data validation at all.

friends = List() 
friends[0] = "hello"
```

"""
class List(Container, MutableSequence, TrackableMixin):
    '''A List that validates content before addition or removal'''

    def __init__(self, T=Converter):
        '''Initializes a List<T> Container'''
        if not isinstance(T, type): raise ValueError("T must be a class")
        if isinstance(T, Collection): raise ValueError("You cannot put a Collection in a List<T>")
        if isinstance(T, Container): raise ValueError("You cannot put a Container in a List<T>")
        if not issubclass(T, (Converter, Model)): raise ValueError("T must be a Converter")
        self.type = T
        self.validate = Reference(T) if issubclass(T, Model) else T()
        self.__store__ = []
        self.__tracker__ = Tracker(self)

    def prepend(self, value):
        '''Adds an item to the front of the list'''
        self.insert(0, value)
        operation = self.__tracker__.op(code=OpCode.PREPEND, instance=self, index=0, value=value)
        self.__tracker__.track(operation)
        
    def insert(self, index, value):
        '''Validate and possibly transform value before insertion'''
        __size__(value)
        __length__(self)
        value = self.validate(value)
        self.__store__.insert(index, value)
        operation = self.__tracker__.op(code=OpCode.INSERT, instance=self, index=index, value=value)
        self.__tracker__.track(operation)

    def __setitem__(self, index, value):
        '''Validate and possibly transform value before adding it to @self'''
        __size__(value)
        __length__(self)
        value = self.validate(value)
        self.__store__[index] = value
        operation = self.__tracker__.op(code=OpCode.INSERT, instance=self, index=index, value=value)
        self.__tracker__.track(operation)
        
    def __getitem__(self, index):
        value = self.__store__[index]
        return value
        
    def __str__(self):
        return str(self.__store__)

    def __contains__(self, item):
        value = self.validate(item)
        return value in self.__store__

    def __delitem__(self, index):
        del self.__store__[index]
        operation = self.__tracker__.op(code=OpCode.DELETE, instance=self, index=index)
        self.__tracker__.track(operation)
        
    def __len__(self):
        return len(self.__store__)

    def __iter__(self):
        for k in self.__store__:
                yield k

    def __eq__(self, other):
        if isinstance(other, List):
            return self.__store__ == other.__data__
        elif isinstance(other, list):
            return self.__store__ == other
        else:
            return False
    
    
        
"""
Set<T>:
A mutable set that does type validation before adding items to the set. 
By default it behaves like an ordinary set.
"""
class Set(Container, MutableSet, TrackableMixin):
    '''A Set that validates content before addition'''

    def __init__(self, T=Converter):
        """Initializes a Set<T> Container"""
        if not isinstance(T, type): raise ValueError("T must be a class")
        if isinstance(T, Collection): raise ValueError("You cannot put a Collection in a Set")
        if isinstance(T, Container): raise ValueError("You cannot put a Container in a Set")
        if not issubclass(T, (Converter, Model)): raise ValueError("T must be a Converter")
        self.type = T
        self.validate = Reference(T) if issubclass(T, Model) else T()
        self.__store__ = set()
        self.__tracker__ = Tracker(self)

    def add(self, value):
        __size__(value)
        __length__(self)
        value = self.validate(value)
        self.__store__.add(value)
        operation = self.__tracker__.op(code=OpCode.ADD, instance=self, value=value)
        self.__tracker__.track(operation)

    def discard(self, value):
        value = self.validate(value)
        self.__store__.discard(value)
        operation = self.__tracker__.op(code=OpCode.DISCARD, instance=self, value=value)
        self.__tracker__.track(operation)

    def __contains__(self, item):
        value = self.validate(item)
        return value in self.__store__

    def _from_iterable(self, iterable):
        return Set(self.type, iterable)

    def __iter__(self):
        for value in self.__store__:
            yield value

    def __str__(self):
        return str(self.__store__)

    def __eq__(self, other):
        if isinstance(other, Set):
            return self.__store__ == other.__data__
        elif isinstance(other, set):
            return self.__store__ == other
        else:
            return False

    def __len__(self):
        return len(self.__store__)
   