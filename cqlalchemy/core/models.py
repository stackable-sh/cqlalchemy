
import uuid
import json
import inspect
from copy import copy, deepcopy

from ..options import keyspace
from .builtins import object, fields, assertType, assertNotType
from .serialization import dump, quote
from .differ import Differ

from .signals import subscribe, callable
from .signals import SIGNAL_MODEL_SAVED

"""
from cqlalchemy.options import keyspace
from cqlalchemy.storage.db import ModelTable, CounterTable, Expirable, ExpandoTable, AutoCqlQuery
from cqlalchemy.storage.schema import SchemaEditor
"""

__all__ = [ 
    "Model", "Expando", "UUID", "Reference", "Counter", "Property", "Type", "UnIndexable", "UnIndexedType", 
    "READONLY", "READWRITE", "GT", "LT", "GTE", "LTE", "EQ", "IN", "BaseModel"      
]

READWRITE, READONLY = 1, 2
VALUE, COMPLEX, EMPTY = 3, 4, 5  # VALUE TYPES FOR SERIALIZATION.

    
class BadValueError(Exception):
    """An exception that signifies that a validation error has occurred"""
    pass

"""
Converter:
A converter is a single class that contains methods for coercion, validation and transformation from pythonic values 
to data store representations and vice versa, A descriptor is a special converter that is also a python descriptor, 
which allows callers to do coercion, and validation on attributes of their class.
 
Serialization Notes
===================   
During serialization (i.e. when callers invoke the Converter.serialize(val)) method, implementers must return a value or 
throw one of these exceptions - ComplexObjectException,EmptyObjectException, or InvalidObject to the serialization sub-system. 
Any other subsystem will be re-raised by the serialization system to the caller on the next level.
"""
class Converter(object):
    '''The contract for all converters'''
    
    def __call__(self, value):
        '''A shortcut to validate'''
        return self.validate(value)
    
    def validate(self, value):
        '''Basic Definition just returns the value passed to it'''
        return value
    
    def convert(self, instance, value):
        '''Convert the object to its datastore representation'''
        raise NotImplementedError("Implemented in sub classes")
    
    def deconvert(self, value):
        '''Converts a @value which is a datastore repr to a native python object'''
        raise NotImplementedError("Implemented in sub classes")
    
    def saveable(self):
        '''All descriptors can be saved by default'''
        raise NotImplementedError("Implemented in sub classes")
    
    def serialize(self, value):
        '''Transforms the value in this converter into something displayable in JSON'''
        raise NotImplementedError("Implemented in sub classes")
    
    def deserialize(self, value):
        """Transforms a 'potentially unsafe' value from JSON into something suitable for python"""
        raise NotImplementedError("Implemented in sub classes")
  
         
"""
Property:
Base class for all data descriptors which can convert/deconvert; 
"""
class Property(Converter):
    """A Generic Data Property which can be READONLY or READWRITE"""
    counter = 0
    def __init__(self, **keywords):
        """Initializes the Property"""
        mode = keywords.pop("mode", READWRITE)
        default = keywords.pop("default", None)
        if mode not in [READWRITE, READONLY]:
            raise ValueError("@mode must be one of READONLY,READWRITE")
        if mode == READONLY and default is None:
            raise ValueError("You must provide a @default value in READONLY mode")
        self.mode = mode
        self.required = keywords.pop("required", False)
        self.choices = keywords.pop("choices", [])
        self.omit = keywords.pop("omit", False)
        self.name = None
        self.deleted = False
        self.default = default
        if "validator" in keywords and callable(keywords["validator"]):
            self.validator = keywords["validator"]
            self.default = self.validate(default)
        elif keywords.get("validator", None) is None:
            self.validator = None
        else:
            raise ValueError("keyword: validator must be a callable or None")
        self.counter += 1
         
    def __set__(self, instance, value):
        """Put @value in @instance's class dictionary"""
        # We do not support class descriptors in cqlalchemy.
        if self.mode == READONLY:
            raise AttributeError("This is a READONLY attribute")
        value = self.validate(value)
        if self.name is None: 
            name = Property.search(instance, None, self)
            self.configure(name, instance)
        if self.name is not None:
            instance.__dict__[self.name] = value
            if hasattr(instance, "__store__"):
                instance.__store__[self.name] = value
            self.deleted = False
        else:
            raise AttributeError("Cannot find %s in  %s " % (self,instance))
    
    def __get__(self, instance, owner):
        """Read the value of this property"""
        # We do not support class descriptors in cqlalchemy.
        if self.name is None : 
            name = Property.search(instance, owner, self)
            self.configure(name, owner)
        if self.name is not None:
            try:
                if instance is not None:
                    return instance.__dict__[self.name]
                elif owner is not None:
                    return owner.__dict__[self.name]
                else:
                    raise ValueError("@instance and @owner can't both be null")   
            except (AttributeError, KeyError) as error:
                if not self.deleted:
                    if self.mode == READWRITE and self.default:
                        value = deepcopy(self.default)
                        self.__set__(instance, value)
                        return value
                    elif self.mode == READONLY:
                        return self.default
                else:
                    raise AttributeError("Cannot find %s in %s" % (self,instance))
        else:
            raise AttributeError("Cannot find any property named %s in: %s" % 
                (self.name, owner))
           
    def __delete__(self, instance):
        """ Delete this Property from @instance """
        if self.deleted: return 
        if self.mode != READWRITE:
            raise AttributeError("This is NOT a READWRITE Property, Error")
        if self.name is None : 
            name = Property.search(instance, None ,self)
            self.configure(name, instance)
        if self.name is not None:
            try:
                del instance.__dict__[self.name]
                if hasattr(instance, "__store__"):
                    del instance.__store__[self.name]
                self.deleted = True
            except (AttributeError,KeyError) as error: raise error
        else:
            raise AttributeError("Cannot find Property: %s in: %s or its ancestors" 
                % (self,instance))
   
    @staticmethod
    def search(instance, owner, descriptor):
        """Returns the name of this descriptor by searching its class hierachy"""
        '''Search class dictionary first'''
        if instance is not None:
            for name, value in list(instance.__class__.__dict__.items()):
                if value is descriptor:
                    return name
            '''Then search all the ancestors dictionary'''        
            for cls in type(instance).__bases__:
                for name, value in list(cls.__dict__.items()):
                    if value is descriptor:
                        return name
        elif owner is not None:
            for name, value in list(owner.__dict__.items()):
                if value is descriptor:
                    return name
            '''Then search all the ancestors dictionary'''        
            for cls in owner.__bases__:
                for name, value in list(cls.__dict__.items()):
                    if value is descriptor:
                        return name
        return None         
        
    def empty(self, value):
        """What does empty mean to this descriptor?"""
        return value is None
                        
    def validate(self, value):
        """Asserts that the value provided is compatible with this property"""
        if self.required and self.empty(value):
            raise BadValueError("Property: %s is required, it cannot be empty" % self.name) 
        if self.choices:
            if value not in self.choices:
                raise BadValueError("The property %s is %r; it must be on of %r"% (self.name, value, self.choices))
        if self.validator is not None:
            value = self.validator(value)
        return value
          
    def configure(self, name, owner):
        """Allow this property to know its attribute name, and the class it belongs to"""
        if getattr(self, "configured", False): 
            return
        self.name = name
        self.owner = owner if isinstance(owner, type) else owner.__class__
        self.configured = True
    
    def __str__(self):
        '''String representation of a Property'''
        return "{self.__class__}: {self.name}".format(self=self)


"""
CqlProperty:
Represent a property that can be converted to CQL and persisted to cassandra.
As a distinction, all CqlProperty objects expect an optional 'key', and 'indexed'
property which allow you to create compound/clustering keys and allow indexing.
"""
class CqlProperty(Property):
    '''A Property object that can be stored and queried in cassandra using CQL'''
    type, ctype = None, None

    def __init__(self, **keywords):
        '''Calls the super constructor, and adds the ability to make properties keys'''
        self.key = keywords.pop("key", False)
        self.primary = keywords.pop("primary", False)
        self.index = keywords.pop("index", False)
        self.static = keywords.pop("static", False)
        self.ttl = keywords.pop("ttl", None)
        if self.primary:
            self.key = True
        super(CqlProperty, self).__init__(**keywords)
    
    def validate(self, value):
        """Asserts that the value provided is compatible with this property"""
        if self.key and self.empty(value):
            raise BadValueError("Property: %s is a key; hence its required, it cannot be empty" % self.name) 
        return super(CqlProperty, self).validate(value)
        
    def indexed(self):
        '''Checks if this property should be indexed'''
        if not self.saveable():
            return False
        return self.index
    
    def saveable(self):
        return True

"""
UnIndexable:
The base class of all Properties that cannot be indexed. 
"""
class UnIndexable(CqlProperty):
    '''A Property that cannot be indexed'''
        
    def indexed(self):
        '''An un-indexable property cannot be indexed'''
        return False

'''
Collection:
Makes sure that users cannot swap collections descriptor attribute to new objects at run time, so they don't mess up 
the internal differ of each typed collection, or else data might get lost during use.
'''
class Collection(UnIndexable):
    '''The base class of all Collection descriptors.'''
    
    def __init__(self, **keywords):
        '''Generic init code for cql collections'''
        if "key" in keywords: 
            raise BadValueError("Collection objects do not support the 'key' argument")
        if "indexed" in keywords: 
            raise BadValueError("Collection objects do not support the 'indexed' argument")
        super(Collection, self).__init__(**keywords)
    
    def __set__(self, instance, value):
        '''Prevents users from overwriting this variable with new data'''
        if self.name is None:
            raise AttributeError("This descriptor doesn't exist with {instance}".format(instance=instance))
        found = getattr(instance, self.name)
        if found:
            raise AttributeError("You cannot overwrite an existing Collection.")
        else:
            super(Collection, self).__set__(instance, value)
    
    def commit(self):
        """Allows the descriptor to commmit changes to itself"""
        raise NotImplementedError("Implemented in subclasses")
    
    
"""
UnSaveable:
The base class of all descriptors that cannot be saved.
"""
class UnSaveable(Property):
    '''A Property that cannot be persisted'''
    
    def saveable(self):
        '''All unsaveable descriptors cannot be saved'''
        return False
    
'''
Default:
Used to provide validation/conversion/deconversion for the dynamic attributes of 
Expando and similar objects.
'''
class Default(UnSaveable):
    '''Used to create default descriptors for Models'''

    def __init__(self, K=Converter, V=Converter):
        '''Simple stash for Descriptors for  Models'''
        assertType(K, Converter)
        assertType(V, Converter)
        assertNotType(K, Collection)
        assertNotType(V, Collection)
        key = K() if inspect.isclass(K) else K
        value = V() if inspect.isclass(V) else V
        self.key = key 
        self.value = value 
        super(Default, self).__init__()

    def __set__(self, instance, value):
        """Put @value in @instance's class dictionary"""
        raise AttributeError("the Default property is readonly, you cannot change it.")
    
    def __get__(self, instance, owner):
        """Read the value of this property"""
        return self.key, self.value
           
    def __delete__(self, instance):
        """ Delete this Property from @instance """
        raise AttributeError("the Default property is readonly, it cannot be deleted")
    
    def configure(self, name, owner):
        """Does not do anything"""
        pass   
          
"""
Type:
A Descriptor that provides CQL aware type coercion, checking and validation. 
"""
class Type(CqlProperty):
    """Does type checking and coercion"""

    def __init__(self, **keywords):
        self.type = keywords.pop("type", None) if self.type is None else self.type #LEAVE OLDER TYPES
        super(Type, self).__init__(**keywords)
    
    def __call__(self, value):
        """A shortcut to self.validate(value)"""
        return self.validate(value)
    
    def validate(self, value):
        """Add type checking and coercion and automatic construction to basic validation"""
        value = super(Type,self).validate(value)
        if self.type is None:
            return value
        if value is not None and not isinstance(value, self.type):
            try:
                if isinstance(value, list) or isinstance(value, tuple): value = self.type(*value)
                elif isinstance(value, dict): value = self.type(**value)
                else: value = self.type(value)
            except: 
                raise BadValueError("Cannot coerce: %s to %s"% (value, self.type))
        return value

"""
Basic:
Represents a type that you can convert, serialize with the str builtin function.
We allow for the deconvert function to be implemented by the subclass.
"""
class Basic(Type):
    '''A Type that can be converted with str'''
    type, ctype = str, "text"
    
    def serialize(self, value):
        """Basic types return str(val) during serialization regardless of format"""
        return str(value)
    
    def deserialize(self, value):
        """Basic types return str(val) during serialization regardless of format"""
        return self.type(value)
        
    def convert(self, instance=None, value=None):
        '''Defines insert behavior for basic python types'''
        from cqlalchemy.core.types import blob
        value = self.validate(value)
        if value is None:
            raise BadValueError("We cannot convert 'None' to a native type for property: %s" % self.name)
        if isinstance(value, str):
            return quote(value)
        if isinstance(value, bool):
            value = "true" if value else "false"
            return value
        if isinstance(value, blob):
            value = dump(value)
            return value
        val = self.type(value)
        return str(val)
        
    def __insert__(self, instance=None, value=None):
        '''Defines insert behavior for basic python types'''
        return self.convert(instance, value)
    
    def __update__(self, instance=None, value=None):
        '''Defines update behavior for basic python types'''
        assertType(instance, Model)
        value = self.convert(instance, value)
        return "{name} = {value}".format(name=self.name, value=value)
    
    
"""
UnIndexedType: A Type that cannot be indexed
"""
class UnIndexedType(UnIndexable, Type):
    '''A Type that cannot be indexed'''
    pass

"""
ExpiryProperty:
The Expiry property for Model objects.
"""
class ExpiryProperty(UnSaveable):
    '''An unsaveable descriptor that allows you to make a model expire'''

    def __get__(self, instance, owner):
        """Returns the set expiry value or the default one"""
        result = super().__get__(instance, owner)
        if not result:
            return owner.__options__.get("expiry", 0)
        else:
            return result
    
    def validate(self, value):
        '''You can only set positive integers/longs here'''
        if not isinstance(value, int):
            try:
                value = int(value)
                return value
            except Exception:
                raise BadValueError("You can only set values that can be converted to numbers here.")
        return value
        
"""
Reference:

A Pointer to another Model that has been presuambly persisted in the datastore. 
The Reference property is not fool hardy i.e. It does not verify if the Model it points to exists or not 
on cassandra, it only checks that the model you are trying to set on it has a complete key. 

Reference properties only store the `key` of a model in Cassandra. At read/access time, the property attempts 
to read out the model with the `key` stored by the Reference property if and only if the attribute which the 
property describes is None. It may be possible that this Reference points to a Model that no longer exists
(perhaps it was deleted, or not saved), in this case, the Reference Property returns 'None' when you try to read 
from it in another session.

Reference properties can be indexed and queried against naturally i.e using Model/Expando instances, the 
descriptor handles the conversion and deconversion of Models/Expando transparently during queries.

Here's how to use a Reference:

```python

class Person(Model):
    name = String()
    email = String(index=True)

class Book(Model):
    name = String(index=True)
    owner = Reference(Person, index=True) # Points to a stored Person.

person = Person.create(email="cody@liverpool.com", name="Cody Gakpo")
book = Book.create(name="War & Peace", owner=person)

# Later on, you could retreive the Reference or even find a book with it.

book = Book.objects.where(name="War & Peace").one()
assert book.owner.name == "Cody Gakpo"

# Find book by author index.
books = Book.objects.where(author=person).all()
```
"""  
class Reference(Basic):
    '''A Pointer to another persisted Model'''
    
    def __init__(self, kind, **keywords):
        '''Override the properties constructor'''
        from cqlalchemy.connection.table import Schema

        if not issubclass(kind, (str, BaseModel)):
            raise BadValueError("the class for a Reference has to be a str or BaseModel")
        self.kind = kind if inspect.isclass(kind) else Schema.discover(kind)
        super(Reference, self).__init__(**keywords)

    def convert(self, instance=None, value=None):
        '''Insert behaviour for Reference descriptors'''
        assertType(value, BaseModel); 
        value = self.validate(value)
        key = fields(value, CqlProperty).get("id")
        id = key.convert(value, value.id) 
        pointer = {"keyspace" : self.kind.keyspace(), "kind" : value.kind(), "id" : id}
        value = dump(pointer) 
        value = quote(value)
        return value
        
    def deconvert(self, value):
        '''Changes a stored Reference to its Model'''
        from cqlalchemy.connection.table import Schema

        if value is None: return None
        dict = json.loads(value)
        if not bool("id" in dict and "keyspace" in dict and "kind" in dict):
            raise BadValueError("CqlAlchemy cannot load an invalid Reference")
        kind = Schema.discover(dict["kind"])
        if kind:
            return kind.__table__.read(dict["id"])
        else:
            return None
         
    def validate(self, value):
        '''Makes sure you can only set a Model that is complete on a Reference'''
        from cqlalchemy.connection.table import Schema

        if self.empty(value):
            return None   
        if isinstance(self.kind, str):
            found = Schema.discover(self.kind)
            if found: 
                self.kind = found     
        if not isinstance(value, (self.kind, BaseModel)):
            raise BadValueError("Value: {0} must be an instance of {1}".format(value, self.kind)) 
        value.validate() #Finally validate the model then return it.
        return value 
    
    def __eq__(self, other):
        '''Two Reference objects are equal if they contain a pointer to the same class'''
        if not type(self) == type(other):
            return False
        return other.kind == self.kind
        
    def __str__(self):
        '''Returns a str representation of this Reference'''
        return str(self)

'''
ObjectsProperty:
is the property that allows you to build queries fluently with a Model. It automatically creates new query objects
whenever its descriptor is accessed.
'''
class ObjectsProperty(UnSaveable):
    '''Allows us to automatically create new AutoCqlQuery objects.'''
    
    def __get__(self, instance, owner):
        '''Everytime objects is accessed create a new AutoCqlQuery instance'''
        from cqlalchemy.connection.cql import AutoCqlQuery
        return AutoCqlQuery(owner)

"""
UUID:
Generates Type 4 UUIDs on the fly when they are requested for; this is
useful for creating UUID's for Models.
"""
class UUID(Type):
    '''A type 4 UUID Property'''
    type, ctype = str, 'uuid'

    def __init__(self, **keywords):
        '''Simply makes sure that a UUID Property is READWRITE'''
        super(UUID,self).__init__(**keywords)
        
    def validate(self, value):
        '''Validates UUID objects.'''
        try:
            if value is None:
                return uuid.uuid4()
            if isinstance(value, uuid.UUID): 
                return value
            try:
                coerced = uuid.UUID(value)
            except Exception as e:
                coerced = uuid.UUID(bytes=value)
            return coerced
        except Exception as e:
            raise BadValueError("Could not convert %s to a Type 4 UUID" % value)
                
    def __get__(self, instance, owner):
        """Read the value of this property"""
        if self.name is None : self.name = UUID.search(instance, owner, self)
        if self.name is not None:
            try:
                value = None
                if instance is not None:
                    value = instance.__dict__.get(self.name, None)
                elif instance is None and owner is not None:
                    value = owner.__dict__.get(self.name, None)
                else:
                    raise ValueError("@instance and @owner can't both be null")
                if value is None:
                    value = uuid.uuid4()
                    self.__set__(instance, value)
                return value  
            except (AttributeError,KeyError) as error:
                raise error
        else:
            raise AttributeError("Cannot find any property named %s in: %s" % 
                (self.name, owner))
        
    def __insert__(self, instance=None, value=None):
        '''Converts the basic type with the str operation, which we can do an eval() on.'''
        value = self.validate(value)
        return str(value)
    
    def __update__(self, instance=None, value=None):
        '''Converts the basic type with the str operation, which we can do an eval() on.'''
        assertType(instance, Model)
        value = self.convert(instance, value)
        return "%s = %s" % (self.name, value)
            
    def deconvert(self, value):
        '''Convert the UUID bytes to a python object'''
        if value is None:
            return None
        else:
            created = None
            try:
                created = uuid.UUID(bytes=value)
            except Exception: # If it breaks, then we are dealing with a string uuid.
                created = uuid.UUID(value)
            return created   
    
    def convert(self, instance=None, value=None):
        '''Converts the basic type with the str operation, which we can do an eval() on.'''
        value = self.validate(value)
        return str(value)
        
    def serialize(self, value):
        """Basic types return str(val) during serialization regardless of format"""
        value = self.validate(value)
        return str(value)
    
    def deserialize(self, value):
        """Basic types return str(val) during serialization regardless of format"""
        return self.deconvert(value)  

                  
"""
BaseModel:
The super class of all Model related objects. All Model like objects should support dict 
like access/modification/deletion.
"""
class BaseModel(object):
    '''The objects that all Models inherit'''
    
    def __init_subclass__(cls, keyspace=None, expire=0, version=True,  **keywords):
        """Initializes meta variables for BaseModels"""
        super().__init_subclass__(**keywords)
        cls.__options__ = {}
        cls.__options__["keyspace"] = keyspace
        cls.__options__["expire"] = expire
        cls.__options__["version"] = version
        
    def __new__(cls):
        '''Customizes all Model instances to include special hidden attributes'''
        cls.__properties__ = fields(cls, Property)
        cls.__fields__ = fields(cls, CqlProperty)
        instance = object.__new__(cls)
        instance.__store__ = {} # Created for the differ module
       
        # Wire change data capture mechanism 
        instance.differ = Differ(instance, exclude=["differ", "expire"])
        handler = callable(instance.differ.commit)
        subscribe(SIGNAL_MODEL_SAVED, subscriber=handler, sender=instance)
        for name, property in cls.__fields__.items():  
            if isinstance(property, Collection):
                handler = callable(property.commit)
                subscribe(SIGNAL_MODEL_SAVED, subscriber=handler, sender=instance)
        return instance
    
    @classmethod
    def kind(cls):
        """The table name of this class."""
        return cls.__name__
    
    @classmethod
    def keyspace(cls):
        """"Returns the keyspace of this Table, falling back on the configured option"""
        found = cls.__options__.get("keyspace", None)
        if found:
            return found 
        return keyspace()
    
    def keys(self):
        '''Returns a list of all the property name.'''
        return copy(list(self.__store__.keys()))
    
    def values(self):
        '''Returns all the values in this Model excluding the value for the key property'''
        result = []
        for name in self.keys():
            result.append(self[name])
        return copy(result)
    
    def __setitem__(self, key, value):
        '''Allows dictionary style item sets to behave properly'''
        if key in self.__properties__:
            setattr(self, key, value) 
        else:
            self.__store__[key] = value
    
    def __getitem__(self, key):
        '''Allows dictionary style item access to behave properly'''
        return self.__store__[key]
    
    def __delitem__(self, key):
        '''Allows dictionary style item deletions to work properly'''
        if key in self.__properties__:
            delattr(self, key) 
        else:
            del self.__store__[key]
    
    def __contains__(self, key):
        '''Does this model contain this key'''
        return key in self.__store__
            
    def items(self):
        '''Returns a copy of key value pair of every property in the Model'''
        results = []
        for name in self.keys():
            results.append((name, self[name]))
        return results
            
    def iterkeys(self):
        '''Yields all the keys one by one'''
        for i in self.keys():
            yield i
    
    def itervalues(self):
        '''Yields all the values one by one'''
        for i in self.values():
            yield i
        
    def iteritems(self):
        '''Yields a key, value pair of each object'''
        results = []
        for name in self.keys():
            yield name, self[name]
            
    def __len__(self):
        '''How many properties are contained in this object'''
        return len(self.__store__)
    
    def __unicode__(self):
        """Unicode representation of this model"""
        return '%s' % str(self)
    
"""
Expando:

This is a Model to which you can add key/value pairs arbitrarily. 
Expando gives you a *wide* & expandable row object through a dict like protocol which can be stored/read 
in batches from Apache Cassandra.

Expando is useful when you need wide rows, or when you need to build a prototype very quickly without completely figuring 
out your data model in advance. Like Model, Expando keeps track of the changes you make to it, and it persists those changes 
in a batch when you invoke 'save'. Unlike Model, you can store/read individual properties without saving the 
entire Expando object using its get/put methods.

Expando is innately aware of the TTL for each property you store/read to it; unlike Model you can dynamically 
modify the TTL for each of the properties of expando when you store them using its 'put' method, and Expando also keeps 
track of the TTL of properties which it reads from the data store so that properties which have expired on Cassandra, 
expire on Expando roughly at the same time without any significant extra computational overhead. 
Like Model you may also control the TTL for the entire Expando by setting the Expando.expire property on your instance.

Finally, Expando keys are required to be alphanumeric characters and values are any hashable, and 
pickleable python object for maximum flexibility. 

LIMITATIONS
============
It is tempting to use Expando as a cache; we *strongly* advise you not to do so, because 
Expando can only support a maximum of 65,535 keys, and 2GB of size due to internal C* limitations.

We have  designed and provided the appropriately named cache package for ephemeral storage. 

Here's how you use an Expando:

```python
class Author(Expando):
    pass

instance = Author.create(name="Sam Harris", age=49, category="Philosophy")
id = instance["id"] 

author = Author.read(id)
assert author["name"] == "Sam Harris"
assert author["age"] == 49
assert author["category"] == "Philosophy"

author["name"] = "Shakespeare"
author["address"] = "#10 Downing Street, London"
author["age"] = 53
author["publisher"] = "Barnes & Noble, Inc"
author.save()                                                                        # SAVE ENTIRE OBJECT INTO C* IN A BATCH

name = author.get("name")                                                            # SINGLE GET FROM C* 
name, category address = author.get("name", "category", "address")                   # MULTI GET FROM C*
author.put({"name" : "Sun Tzu", "address" : "1, Santa Clara, California"})           # MULTI SET IN BATCH
author.put({"name": "Confucius"}, ttl=20)                                            # SAVE WITH TTL

authors = Author.objects.all()                                                      # RETRIEVE ALL AUTHORS
results = Author\
    .objects\
    .contain(entry=("name", "Sun Tzu"))\                                            # FIND ALL AUTHORS WITH AN ENTRY
.execute()

results = Author
    .objects
    .contain(value="Sun Tzu")
.execute()                                                                          # FIND ALL AUTHORS THAT HAVE THIS VALUE
```
"""
class Expando(BaseModel):
    '''A dynamically expandable and durable object'''
    
    def __new__(cls, *arguments, **keywords):
        '''Customizes all Model instances to include special attributes'''
        from cqlalchemy.core.commons import Name, Pickle
        from cqlalchemy.connection.table import ExpandoTable

        if not hasattr(cls, "id"):
            cls.id = UUID()
        if not hasattr(cls, "default"):
            cls.default = Default(Pickle, Pickle)
        if not hasattr(cls, "expire"):
            cls.expire = ExpiryProperty()

        cls.__table__ = ExpandoTable(cls)
        instance = BaseModel.__new__(cls, *arguments, **keywords)
        return instance
    
    def __init__(self, **keywords):
        '''Basic initialization'''
        super(Expando, self).__init__()
        for name, value in list(keywords.items()):
            self[name] = value
        self.__saved__ = False
    
    @classmethod
    def create(cls, arguments={}, unique=False):
        '''Creates a new Expando, saves it and then returns it'''
        instance = cls()
        for name in arguments:
            instance[name] = arguments[name]
        instance.save(unique)
        return instance
        
    def saved(self):
        """Returns True if this object has been saved at least once, and its keys have not changed."""
        if not self.__saved__:
            return False
        dirty = "id" in self.differ.changed()
        return self.__saved__ and not dirty
    
    def validate(self):
        '''Checks that this Expando has a valid key'''
        key = getattr(self.__class__, "id", None)
        if key:
            value = getattr(self, "id", None)
            if key.empty(value):
                raise BadValueError("Your Expando key cannot be empty")
            return
        raise BadValueError("Your Expando doesn't have a valid key")
    
    def __setitem__(self, key, value):
        '''Allows dictionary style item sets to behave properly'''
        if key == "id":
            setattr(self, key, value) 
        else:
            k, v = self.default
            key, value = k.validate(key), v.validate(value)
            self.__store__[key] = value
    
    def __delitem__(self, key):
        '''Allows dictionary style item deletions to work properly'''
        if key == "id":
            delattr(self, key) 
        else:
            k, v = self.default
            key = k.validate(key)
            del self.__store__[key]
      
    def __getitem__(self, key):
        '''Allows dictionary style item access to behave properly'''
        from cqlalchemy.core.types import Expirable

        k, v = self.default
        key = k.validate(key)
        value = self.__store__.get(key, None)
        if value:
            if isinstance(value, Expirable): #Retreive the value if its an Expirable
                return value.get()
            else: 
                return value
        else: # Try to Fetch the key from Apache Cassandra if this value doesn't exist.
            value = self.get([key,])[0]
            if value:
                return value
            else: # Raise key error if we couldn't find this key on Cassandra.
                return None
    
    def __contains__(self, key):
        '''Does this model contain this key'''
        if key in self.__store__:
            try:
                value = self[key] # value is irrelevant.
                return True
            except KeyError:
                return False
    
    def get(self, *properties):
        '''Reads multiple properties from the datastore'''
        all = True if not properties else False
        if all:
            return self.__table__.get(self, all=True)
        else:
            return self.__table__.get(names=properties)
        
    def put(self, properties=None, ttl=None):
        '''Alternative set method, which allows multi-set and ttl values'''
        if not isinstance(properties, dict):
            raise ValueError("We require a dictionary of keys here")
        for name, value in properties.items():
            self[name] = value 
        self.__table__.put(self, properties, ttl)
        self.__saved__ = True 
    
    def has(self, key=None, value=None, entry=None):
        """Checks if this Expando has a particular property saved, uses a network called to C* as last resort"""
        pass 

    def save(self, unique=False):
        '''Saves this Expando to Cassandra'''
        self.__table__.save(self, unique)
    
    @classmethod
    def upsert(cls, **data):
        """Updates an already existing Expando instance in the datastore"""
        return cls.__table__.upsert(**data)
            
    @classmethod
    def read(cls, id, properties=None):
        '''Read an expando from the data store'''
        return cls.__table__.read(id, properties)
    
    @classmethod
    def delete(cls, *keys):
        """Deletes one or many Expando objects from the data store"""
        cls.__table__.delete(*keys)
    
    def __eq__(self, other):
        '''Checks if two Expando objects are equal'''
        if not type(other) == type(self):
            return False 
        us = getattr(self, "id", None)
        them = getattr(other, "id", None)
        return us == them
                  

"""
Vector:

This is a durable Vector object for C*, which supports LIFO or FIFO semantics.

You can store any object that can be pickled into a Vector. Operations on Vector happens in batches to 
improve reliablity since Vector is not idempotent. Vectors are useful when you want to persist a large (automatically) 
indexed contiguous list of similar objects to C*, in order to query and operate upon later.

Vector is also an innately TTL aware Entity.

LIMITATIONS
============
1. Vector can only support a maximum of 65,535 objects and 2GB in memory due to internal C* limitations. 
2. Operations on Vector are not idempotent; if you need idempotency consider using a Block, or Expando. 
3. Vector is not synchronized; the underlying representation may be modified by another C* client concurrently (unless you use Locks).
4. Vector fetches its entire data into memory upon query, please keep this in mind to manage memery pressure for your application

This is how to use a Vector:

```python
class Basket(Vector):
    pass

# Create a Basket and add some fruits, and persist it to C*

fruits = Basket.create(["Apple", "Banana", "Watermelon", "Grapes"])
id = fruits["id"] 
assert id is not None

# Retrieve the entire Basket in another session

fruits = Basket.read(id)
assert fruits[0] == "Apple"
assert len(fruits) == 4

# You can prepend, extend, remove, and append objects to the Basket

fruits.append("Carrot")
fruits.extend(["Orange", "Cucumber", "Mango"])
fruits.prepend("Guava")
fruits.insert(3, "Plantain")
del fruits[6]     #  Equivalent to fruits.delete(6, execute=False)


# Save Vector to C*, in a network efficient way. 
fruits.save()

# Read the Basket from another session, and verify the data you've persisted
fruits = Basket.read(id)
assert fruits[0] == "Guava"
assert "Carrot" in fruits
assert "Mango" not in fruits

# You can also update/delete data immediately in place. However, you should know that 
# executing your change incurs the cost of an immediate network call to C* to effect that change;
# but this also has the advantage of saving you from rewriting the entire/or large parts of list to C*  
* upon save. 

fruits.insert(0, "Lemon", execute=True)
fruits.pop(0, execute=True)
fruits.remove("Carrot", execute=True)    

# You can provide a TTL when you append or prepend new objects into a Vector
fruits.append("Cashew", ttl=10, execute=True)
fruits.prepend("Strawberries", ttl=0, execute=True)

# You may query all instances of Basket, 
for basket in Basket.objects.all():
    print(basket)

# Or search for a specific Fruit in all the Basket(s)
results = Basket
    .objects
    .contain("Pear")                                             
.execute()
```
"""
class Vector(BaseModel):
    """A Durable One Dimensional Vector"""
    pass 


"""
Block:

This is a durable unorderd Set for C*.

You can store any object that can be pickled into a Block. Operations on Vector happens in batches to 
improve performance. Blocks are useful when you want to persist a large (automatically) indexed contiguous set
of similar objects to C*, in order to query and operate upon later.

Unlike Vector, operations on Block are idempotent. Set is also an innately TTL aware Entity.

LIMITATIONS
============
1. Block can only support a maximum of 65,535 objects, and 2GB in memory due to internal C* limitations.  
4. Vector fetches its entire data into memory upon query, please keep this in mind to manage memery pressure for your application

This is how to use a Block:

```python
class Basket(Block):
    pass

# Create a Basket and add some fruits, and persist it to C*

fruits = Basket.create(["Apple", "Banana", "Watermelon", "Grapes"])
id = fruits["id"] 
assert id is not None

# Retrieve the entire Basket in another session

fruits = Basket.read(id)
assert len(fruits) == 4
for fruit in fruits:
    print(fruit)

# You can add and remove objects from the Basket idempotently. 

fruits.add("Carrot")
fruits.extend(["Orange", "Cucumber", "Mango"])
fruits.remove("Guava")

# Save Block to C*, in a network efficient way using a batch containing all operations. 
fruits.save()

# You can also update/delete data, immediately in place. 
# Executing your change incurs the cost of a network call to C*, but it also saves you from having 
# to sending large data set over the wire upon batch save. 

fruits.add("Lemon", execute=True)

# You can provide a TTL when you add new objects into Block
fruits.add("Cashew", ttl=10, execute=True)

# You may query all instances of Basket, 
for basket in Basket.objects.all():
    print(basket)

# Or search for a specific Fruit in all the Basket(s) in C*
results = Basket
    .objects
    .contain("Pear")                                             
.execute()
```
"""
class Block(BaseModel):
    """A C* Durable Set"""
    pass 



"""    
Model: 

This is the basic unit of persistence for cqlalchemy. We recommend the use of Model when 
you want to store clearly defined things to Cassandra. 

A Model is always aware of the changes you make to it; ergo models persist only changes you make to them; 
thereby saving bandwidth and unnecessary network connections to the datastore service. A Model also 
knows the best way to save changes made to it; it knows when to batch changes one update query, and when to 
execute updates/deletes in multiple sequential queries - either ways, It cleanly maps your object to Apache 
Cassandra consistently and performantly.

Models are very performat because they take advantage of Cassandra's inbuilt caching/compresssion system, 
and they are very versatile to use because they allow you to store properties (with support for all sorts of 
interesting descriptors - see the cqlalchemy/core/commons module), index them, query for them, update them 
(including using conditional updates), and even control their TTL as a group.

Models also make the use of compound keys for your Model transparent to you. Models are the way to
go when you want to store clearly defined objects in Cassandra.

Model is designed to be used when you intend to store an object with properties which you know before hand; 
on the other hand, you can inherit from Expando if you're unsure of your data model before hand 
(maybe during prototyping), or when you just want to store objects with alot of properties (Wide Rows).

Here is a simple Model

```python
class Profile(Model):
    name = String(index=True, required=True)
    gender = String(choices=('M', 'F',))

person = Profile.create(name="Iroiso", gender='M')
```
"""
class Model(BaseModel):
    '''Unit of Persistence'''

    def __new__(cls, *arguments, **keywords):
        '''Customizes all Model instances to include special attributes'''
        from cqlalchemy.connection.table import ModelTable

        instance = BaseModel.__new__(cls)
        if not hasattr(cls, "id"):
            cls.id = UUID()
        if not hasattr(cls, "expire"):
            cls.expire = ExpiryProperty()
        
        cls.__table__ = ModelTable(cls)
        cls.__keys__ = set()
        cls.objects = ObjectsProperty()
        for name, value in list(cls.__properties__.items()):
            if name.startswith("_"):
                raise BadValueError("A Model property name cannot begin with an underscore")
            if not name.islower():
                raise BadValueError("All Model property names should be lower case")
            value.configure(name, cls)
            if name == "id":
                cls.__keys__.add(name)
            if hasattr(value, "key") and value.key:
                cls.__keys__.add(name)      
        return instance
        
    def __init__(self, **keywords):
        """Creates an instance of this Model"""
        super(Model, self).__init__()
        for name, value in list(keywords.items()):
            setattr(self, name, value)
        self.__saved__ = False
        
    def validate(self):
        '''Checks if a Model can be persisted to Cassandra'''
        for name, prop in self.__fields__:
            if name == "id":
                value = getattr(self, name)
                if prop.empty(value):
                    raise BadValueError("Every Model must have a valid id")
            elif hasattr(prop, 'required') and prop.required:
                value = getattr(self, name)
                if prop.empty(value):
                    raise BadValueError("Property: %s is required" % name)
            elif hasattr(prop, 'key') and prop.key:
                value = getattr(self, name)
                if prop.empty(value):
                    raise BadValueError("Property: %s is a key so its required" % name)
    
    def save(self, unique=False, when={}):
        """Stores this Model in Cassandra in one batch update."""
        self.validate()
        # Persist the model to Cassandra
        if self.saved():
            self.__table__.update(self, when)
        else:
            self.__table__.insert(self, unique)
        self.__saved__ = True # Mark this model as saved.
    
    def saved(self):
        """Returns True if this model has been saved before, and its keys have not changed since then."""
        if not self.__saved__:
            return False
        changed = False
        for key in self.__keys__:
            if key in self.differ.changed():
                changed = True
        return self.__saved__ and not changed
    
    @classmethod
    def create(cls, arguments={}, unique=False):
        '''Creates a new Model, saves it and then returns it'''
        instance = cls()
        for name in arguments:
            instance[name] = arguments[name]
        instance.save(unique)
        return instance
    
    @classmethod
    def upsert(cls, data, when={}):
        """Updates an already existing model instance in the datastore."""
        instance = cls(**data)
        cls.__table__.update(instance, when)
        return instance 
    
    @classmethod
    def read(cls, id):
        """Retreives objects from the data store"""
        found = cls.__table__.read(id)
        if found:
            found.__saved__ = True
        return found
        
    @classmethod
    def delete(cls, *keys):
        """Deletes this Model from the data store"""
        cls.__table__.delete(*keys)
    
    def __eq__(self, other):
        '''Two Models are equal if and only if their keys are equal'''
        if not isinstance(other, type(self)):
            return False
        eq = True
        for key in self.__keys__:
            if key in other:
                eq = self[key] == other[key]
        return eq



"""
Counter:

Provides C* backed counter objects for use in your applications - without the 
risk of anti-patterns.

Here is a simple Counter:

```python
Analytics = Counter("Analytics", ["users", "errors", "views"])
stats = Analytics.create()

# You can incr/decr the counter directly on C* 

stats.incr("views")
stats.incr("users", 100)
stats.decr("errors")
```

How to fetch an already existing Analytics object from C*

```python
stats = Analytics.read(key)
print("Active Accounts: %s" % stats.get("users"))
users, errors = stats.get("users", "errors")                # You can fetch multiple counters in one request. 
print(f"Errors : {users}, Users : {errors}")

```
"""
class Counter(BaseModel):
    pass 




       