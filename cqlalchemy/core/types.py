
import re
import sys
import json
import copy
import base64
import hashlib
from collections.abc import MutableMapping, MutableSet, MutableSequence

from .serialization import Size
from .models import Converter, Reference, Model, CqlCollection


__all__ = ["phone", "blob", "Map", "Set", "List",]


MAX_BYTES_SIZE = 65535
MAX_LENGTH_COLLECTION = 65535

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
        self.checksum = self.__md5__(content)
        
    def __md5__(self, content):
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
        return template.format(
            content=self.content, mimetype=self.mimetype,
            metadata=self.metadata
        )
    
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
Description:
Typed Collections that are useful for the collection descriptors. Typed Collections can be used to 
store collections of Simple Types or Models in Cassandra.
"""

class CollectionException(Exception):
    '''Thrown when you try to do something inappropriate on a collection.'''
    pass

def checkSizeInBytes(*values):
    '''Checks that all the elements in value obey CQL size limits'''
    for value in values:
        if Size.inBytes(value) > MAX_BYTES_SIZE:
            raise CollectionException("Value: %s size in bytes cannot fit into Apache Cassandra" % str(value))

def checkCollectionLength(value):
    '''Checks that len(value) are within CQL length limits'''
    if len(value) > MAX_LENGTH_COLLECTION:
        raise CollectionException("Value: %s length cannot fit into Apache Cassandra" % str(value))


"""
TypedCollection:
A base class for all typed collections.
"""
class TypedCollection(object):
    '''A base class for all typed collections'''
    def commit(self):
        '''All changes to typed collections should be discarded at commit time'''
        raise NotImplementedError("implemented in subclasses")


"""
Map:
A mutable hash table that does type validation before storing items, It behaves like a dict normally.

from cql.core.commons import String, Integer

var = Map(String, Integer)
var['Hello'] = 1

or

# This does not do any data validation at all.

var = Map() 
var[0] = "hello"

# Alternate configuration for construction.

var = List(String, Integer, data={"Hello", 1})
assert var["Hello"] == 1
"""
class Map(TypedCollection, MutableMapping):
    '''A map that does validation of keys and values'''

    def __init__(self, K=Converter, V=Converter, data={}):
        '''Initialization routine for TypeMap'''
        if not isinstance(K, type): raise ValueError("K must be a class")
        if isinstance(K, CqlCollection): raise ValueError("You cannot put a CqlCollection in a TypeSet :)")
        if isinstance(K, TypedCollection): raise ValueError("You cannot put a TypedCollection in a TypedCollection :)")
        if not issubclass(K, (Converter, Model)): raise ValueError("T must be a Converter")
        
        if not isinstance(V, type): raise ValueError("V must be a class")
        if isinstance(V, CqlCollection): raise ValueError("You cannot put a CqlCollection in a TypeSet :)")
        if isinstance(V, TypedCollection): raise ValueError("You cannot put a TypedCollection in a TypedCollection :)")
        if not issubclass(V, (Converter, Model)): raise ValueError("V must be a Converter")
        
        self.type = (K, V)
        self.K = Reference(K) if issubclass(K, Model) else K()
        self.V = Reference(V) if issubclass(V, Model) else V()

        # Create the underlying data for the Map.
        self.__previous__ = {}
        self.__data__ = {}
        for k, v in data.items():
            self[k] = v
        self.commit()
    
    def __setitem__(self, key, value):
        '''Validate and possibly transform key, value before storage'''
        checkSizeInBytes(key, value)
        checkCollectionLength(self)
        key, value = self.K(key), self.V(value)
        self.__data__[key] = value
    
    def __delitem__(self, key):
        '''Validate and possibly transform key before deletion'''
        key = self.K(key)
        del self.__data__[key]
        
    def __getitem__(self, key):
        '''Validate and possibly transform key before retreival'''
        key = self.K(key)
        value = self.__data__[key]
        return value

    def __iter__(self):
        '''Returns a iterable over the data set'''
        # If we have References with Models in them, read the Models and return them.
        for k in self.__data__:
            yield k
    
    def __str__(self):
        '''String representation of an object'''
        return str(self.__data__)

    def __eq__(self, other):
        if isinstance(other, Map):
            return self.__data__ == other.__data__
        elif isinstance(other, dict):
            return self.__data__ == other
        else:
            return False

    def __len__(self):
        '''Returns the number of the keys in this map'''
        return len(self.__data__)

    def added(self):
        '''Returns all the keys that have been added in this session'''
        added = []
        for name in list(self.__data__.keys()):
            if name not in list(self.__previous__.keys()):
                added.append(name)
        return added
    
    def deleted(self):
        '''Returns all the keys that have been removed from this session'''
        deleted = []
        for name in list(self.__previous__.keys()):
            if name not in list(self.__data__.keys()):
                deleted.append(name)
        return deleted
    
    def modified(self):
        '''Returns all the keys that have been modified in this session'''
        modified = []
        for name in self.__data__:
            if name in self.__previous__:
                if self.__data__[name] != self.__previous__[name]:
                    modified.append(name)
        return modified
        
    def commit(self):
        '''Commit changes to this Map by overwriting the __previous__ variable'''
        self.__previous__ = copy.deepcopy(self.__data__)

"""
List:
A mutable sequence type that does data validation before storing data. By default it behaves like an ordinary list. 
If the data type (the `cls` attribute) of a List is a saved Model, the List stores the key of the Model as `Key` object
instead of pickling the Model itself.

e.g.
from cql.core.commons import String

var = List(String)
var.append("Hello")

or

#This does not do any data validation at all.

var = List() 
var[0] = "hello"

alternate configuration for constructors.
var = List(String, data="Hello")
assert var[0] == 'H'
"""
class List(TypedCollection, MutableSequence):
    '''A List that validates content before addition or removal'''
    def __init__(self, T=Converter, data=[]):
        '''Initializes a List'''
        if not isinstance(T, type): raise ValueError("T must be a class")
        if isinstance(T, CqlCollection): raise ValueError("You cannot put a CqlCollection in a TypeSet :)")
        if isinstance(T, TypedCollection): raise ValueError("You cannot put a TypedCollection in a TypedCollection :)")
        if not issubclass(T, (Converter, Model)): raise ValueError("T must be a Converter")
        self.type = T
        self.validate = Reference(T) if issubclass(T, Model) else T()
        self.__previous__ = []
        self.__data__ = []
        for k in data:
            self.append(k)
    
    def prepend(self, value):
        '''Adds an item to the front of the list'''
        self.insert(0, value)
        
    def insert(self, index, value):
        '''Validate and possibly transform value before insertion'''
        checkSizeInBytes(value)
        checkCollectionLength(self)
        value = self.validate(value)
        self.__data__.insert(index, value)

    def __setitem__(self, index, value):
        '''Validate and possibly transform value before adding it to @self'''
        checkSizeInBytes(value)
        checkCollectionLength(self)
        value = self.validate(value)
        self.__data__[index] = value
        
    def __getitem__(self, index):
        '''Read the item stored at @index, possibly transforming it before returning it'''
        value = self.__data__[index]
        return value
        
    def __str__(self):
        return str(self.__data__)

    def __contains__(self, item):
        value = self.validate(item)
        return value in self.__data__

    def __delitem__(self, index):
        del self.__data__[index]
        
    def __len__(self):
        return len(self.__data__)

    def __iter__(self):
        '''Returns a iterable over the data set'''
        for k in self.__data__:
                yield k

    def __eq__(self, other):
        if isinstance(other, List):
            return self.__data__ == other.__data__
        elif isinstance(other, list):
            return self.__data__ == other
        else:
            return False

    def rewrite(self):
        '''Should we rewrite this list into cassandra totally?'''
        bool = False
        if not self.__previous__:
            bool = True
        elif len(self.__data__) < len(self.__previous__):
            bool = True
        return bool
    
    def modifications(self):
        '''Yields all the indices that have been modified on this list recently'''
        prev = self.__previous__; prepend = None; append = None;
        val = self.__data__
        space = len(val) - max(0, len(prev)-1)
        size = len(prev)

        for i in range(space):
            j = i + size #slice boundary
            sub = val[i:j]
            compare = lambda idx: prev[idx] == sub[idx]
            if compare(0) and compare(-1) and prev == sub:
                prepend = val[:i]; append = val[j:]
                break
        return {"prepend" : prepend, "append" : append}
               
    def commit(self):
        '''Commits the changes made to this list, telling the list to begin to track operations again.'''
        self.__previous__ = copy.deepcopy(self.__data__)
        
"""
Set:
A mutable set that does type validation before adding items
to the set. By default it behaves like an ordinary set.
"""
class Set(TypedCollection, MutableSet):
    '''A Set that validates content before addition'''
    def __init__(self, T=Converter, data=set()):
        if not isinstance(T, type): raise ValueError("T must be a class")
        if isinstance(T, CqlCollection): raise ValueError("You cannot put a CqlCollection in a Set :)")
        if isinstance(T, TypedCollection): raise ValueError("You cannot put a TypedCollection in a TypedCollection :)")
        if not issubclass(T, (Converter, Model)): raise ValueError("T must be a Converter")
        self.type = T
        self.validate = Reference(T) if issubclass(T, Model) else T()
        self.__previous__ = set()
        self.__data__ = set()
        for k in data:
            self.add(k)

    def add(self, value):
        '''Validate and possibly transform value before appending it to @self'''
        checkSizeInBytes(value)
        checkCollectionLength(self)
        value = self.validate(value)
        self.__data__.add(value)

    def discard(self, value):
        '''Validate and possibly transform value before appending it to @self'''
        value = self.validate(value)
        self.__data__.discard(value)

    def __contains__(self, item):
        value = self.validate(item)
        return value in self.__data__

    def _from_iterable(self, iterable):
        '''Overridden to make this behave more like a Set'''
        return Set(self.type, iterable)

    def __iter__(self):
        '''Returns a iterable over the data set'''
        for k in self.__data__:
            yield k

    def __str__(self):
        return str(self.__data__)

    def __eq__(self, other):
        if isinstance(other, Set):
            return self.__data__ == other.__data__
        elif isinstance(other, set):
            return self.__data__ == other
        else:
            return False

    def __len__(self):
        return len(self.__data__)
    
    def added(self):
        '''Returns all the **converted** elements that have been added in the current session'''
        add = []
        for value in self.__data__:
            if value not in self.__previous__:
                add.append(value)
        return add
            
    def deleted(self):
        '''Returns all the elements that have been deleted from the current session'''
        delete = []
        for value in self.__previous__:
            if value not in self.__data__:
                delete.append(value)
        return delete
    
    def commit(self):
        '''Start tracking data in a new session'''
        self.__previous__ = copy.deepcopy(self.__data__)