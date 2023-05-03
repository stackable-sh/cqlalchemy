
import uuid
import json
from copy import copy, deepcopy


from .builtins import object, fields, assertType, assertNotType
from .serialization import jsonify, quote
from .differ import Differ

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
        
    def __insert__(self, instance, value):
        '''Return version of object suitable for a CQL INSERT'''
        raise NotImplementedError("Implemented in sub classes")
    
    def __update__(self, instance, value):
        '''
        In this mode, we want to convert @param value to string fragments that can be used in a CQL UPDATE Query. 
        Here's is a list/description of what implementations need to return to be compatible with home.
        
        1) A string object which contains a single UPDATE assignment which is suitable for the underlying CQL type 
        e.g. the CQL text type return "{name}='{value}'" For more examples, look in the home/core/commons 
        package through the implementation on of Set, List and DateTime
        
        2) A list of strings which contain UPDATE assigments suitable for the underlying CQL type.
        
        3) A dict with the format which contain UPDATE assignments in an "updates"
            {
                "updates" : [], # Contains a list of update assignments
                "deletes" : []  # A list deletions to be used with a DELETE query
            }
        Look through the Map implementation in the cqlalchemy/core/commons to see how we used this construct.
        '''
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
        # We do not support class descriptors in home.
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
        # We do not support class descriptors in home.
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
        self.__indexed = keywords.pop("index", False)
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
        return self.__indexed
    
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
CqlCollection:
Makes sure that users cannot swap collections descriptor 
attribute to new objects at run time, so they don't mess up 
the internal differ of each typed collection, or else data 
might get lost during use.
'''
class CqlCollection(UnIndexable):
    '''The base class of all CqlCollection descriptors.'''
    
    def __init__(self, **keywords):
        '''Generic init code for cql collections'''
        if "key" in keywords: 
            raise BadValueError("CqlCollection objects do not support the 'key' argument")
        if "indexed" in keywords: 
            raise BadValueError("CqlCollection objects do not support the 'indexed' argument")
        super(CqlCollection, self).__init__(**keywords)
    
    def __set__(self, instance, value):
        '''Prevents users from overwriting this variable with new data'''
        if not self.name:
            raise AttributeError("This descriptor doesn't exist with {instance}".format(instance=instance))
        found = getattr(instance, self.name)
        if found:
            raise AttributeError("You cannot overwrite an existing CqlCollection.")
        else:
            super(CqlCollection, self).__set__(instance, value)
    
    
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
Used to provide validation/conversion/deconversion for the dynamic
attributes of Expando objects.
'''
class Default(UnSaveable):
    '''Used to create default descriptors for Models'''
    def __init__(self, key=Converter(), value=Converter()):
        '''Simple stash for Descriptors for  Models'''
        assertType(key, Converter); assertType(value, Converter)
        assertNotType(key, CqlCollection); assertNotType(value, CqlCollection)
        self.key, self.value = key, value
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
A CqlProperty that does type coercion, checking and validation. 
This is base class for all the common descriptors.
"""
class Type(CqlProperty):
    """Does type checking and coercion"""

    # TODO: All types should specify default types.
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
            value = jsonify(value)
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

Here's how to use a Reference property.

```
>> class Person(Model):
        name = String(length=25)
        email = String(index=True)

>> class Book(Model):
        name = String(index=True)
        owner = Reference(Person, index=True) #Points to a stored Person.

>> person = Person(email="mumu@yahoo.com", name="Mumu Agbaya")
>> person.save()

>> book = Book(name="War & Peace", owner=person)
>> book.save()

# Later on, you could retreive the Reference or even find a book with it.

>> book = Book.query(name="War & Peace").one()
>> person = book.owner
>> assert person.name == "Mumu Agbaya"

# Find book by author index.
>> books = Book.query(author=person).all()
```
"""  
class Reference(Basic):
    '''A Pointer to another persisted Model'''
    
    def __init__(self, clasz, default=None, index=False, key=False, required=False):
        '''Override the properties constructor'''
        if not issubclass(clasz, (str, BaseModel)):
            raise BadValueError("the clasz for a Reference has to be a str or BaseModel")
        self.clasz = clasz
        super(Reference, self).__init__(
            default=default, 
            index=index, 
            key=key, 
            required=required
        )
    
    def convert(self, instance=None, value=None):
        '''Insert behaviour for Reference descriptors'''
        assertType(value, BaseModel); 
        value = self.validate(value)
        key = fields(value, CqlProperty).get("id")
        id = key.convert(value, value.id) 
        pointer = {"keyspace" : keyspace(), "kind" : value.kind(), "id" : id}
        value = jsonify(pointer) 
        value = quote(value)
        return value
        
    def __insert__(self, instance=None, value=None):
        '''References are stored as serialized `key` objects in the datastore'''
        assertType(instance, BaseModel)
        return self.convert(instance,value)
        
    def __update__(self, instance=None, value=None):
        '''References are stored as serialized `key` objects in the datastore'''
        assertType(instance, BaseModel)
        value = self.convert(instance, value)
        return "%s = %s" % (self.name, value)
        
    def deconvert(self, value):
        '''Changes a stored Reference to its Model'''
        if value is None: return None
        dict = json.loads(value)
        if not bool("id" in dict and "keyspace" in dict and "kind" in dict):
            raise BadValueError("Home cannot load an invalid Reference")
        clasz = SchemaEditor.findType(dict["kind"])
        if clasz:
            return ModelTable(clasz).read(dict["id"])
        else:
            return None
         
    def validate(self, value):
        '''Makes sure you can only set a Model that is complete on a Reference'''
        if self.empty(value):
            return None   
        if isinstance(self.clasz, str):
            found = ModelTable.discover(self.clasz)
            if found: self.clasz = found     
        if not isinstance(value, (self.clasz, BaseModel)):
            raise BadValueError("Value: {0} must be an instance of {1}".format(value, self.clasz)) 
        value.validate() #Finally validate the model then return it.
        return value 
    
    def __eq__(self, other):
        '''Two Reference objects are equal if they contain a pointer to the same class'''
        if not type(self) == type(other):
            return False
        return other.clasz == self.clasz
        
    def __str__(self):
        '''Returns a str representation of this Reference'''
        return str(self)

'''
ObjectsProperty:
is the property that allows you to build queries fluently
with a Model. It automatically creates new query objects
whenever its descriptor is accessed.
'''
class ObjectsProperty(UnSaveable):
    '''Allows us to automatically create new AutoCqlQuery objects.'''
    
    def __get__(self, instance, owner):
        '''Everytime objects is accessed create a new AutoCqlQuery instance'''
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
Counter:

A Counter allows you to create and manipulate cassandra
counters in an easy way; Counters work a little different
from Models because of the way they are implemented in Apache
Cassandra. 

Here is how to create and use counters in your application:

>>  counter = Counter(       
       name = "PageViews",      
       id = URL(length=10),     
       value = 10               
    )
    
>>  home = counter.new("http://example.com/index.html") 
>>  home.incr()                                             # returns 11
>>  found = counter.read("http://example.com/index.html")
>>  found.decr()                                            # returns 10                                 
>>  found.value()                                           # returns 10                                       
>>  found.delete()                                          # removes counter instance                                     
"""
def Counter(name, id=UUID(), value=1):
    '''Creates a counter meta model with @arguments as schema and returns it'''
    return CounterTable(name, id, value)
        
                  
"""
BaseModel:
The super class of all Model related objects. All Model like
objects should support dict like access/modification/deletion.
"""
class BaseModel(object):
    '''The objects that all Models inherit'''

    def __new__(cls):
        '''Customizes all Model instances to include special hidden attributes'''
        cls.__properties__ = fields(cls, Property)
        instance = object.__new__(cls)
        instance.__store__ = {} # Created for the differ module
        return instance

    def __init__(self):
        self.differ = Differ(self, exclude = ['differ', 'expire',])
    
    @classmethod
    def kind(cls):
        """The Column Family name of this class instances"""
        return cls.__name__
    
    def keys(self):
        '''Returns a copy of all the keys in this model excluding the key property'''
        return copy(list(self.__store__.keys()))
    
    def values(self):
        '''Returns all the values in this Model excluding the value for the key property'''
        result = []
        for name in list(self.keys()):
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
        for name in list(self.keys()):
            results.append((name, self[name]))
        return results
            
    def iterkeys(self):
        '''Yields all the keys one by one'''
        for i in list(self.keys()):
            yield i
    
    def itervalues(self):
        '''Yields all the values one by one'''
        for i in list(self.values()):
            yield i
        
    def iteritems(self):
        '''Yields a key, value pair of each object'''
        results = []
        for name in list(self.keys()):
            yield name, self[name]
            
    def __len__(self):
        '''How many properties are contained in this object'''
        return len(self.__store__)
    
    def __unicode__(self):
        """Unicode representation of this model"""
        return '%s' % str(self)
    
"""
Expando:

Is a Model to which you can add key/value pairs arbitrarily - which is stored under the hood as a wide row in Apache Cassandra. 
So, basically Expando gives you an *infinitely* expandable row object through a dict like protocol which can be stored/read 
from Apache Cassandra.

Even though using an Expando is slightly less performant than Model because Model uses Cassandras' builtin caching/compression 
system while Expando only caches row keys (you wouldn't even notice the difference in practical applications), an Expando is 
still very useful when you need wide rows, or when you need to build a prototype very quickly without completely figuring 
out your data model in advance. Like Model, Expando keeps track of the changes you make to it, and it persists those changes 
in a batch when you invoke 'save'. Unlike Model, you can store/read individual properties without saving the 
entire Expando object using its get/put methods.

As an advantage to make up for skipping the row cache, Expando is innately aware of TTL for each property you store/read to it; 
unlike Model you can modify the TTL for each of the properties of expando when you store them using its 'put' method, and Expando 
also keeps track of the TTL of properties which it reads from the data store so that properties which have 
expired on Cassandra, expire on Expando roughly at the same time without any significant extra computational overhead. 
Like Model you may also control the TTL for the entire Expando by setting the Expando.expire property on your instance.

With Expando, things are much simpler; no indexes, no CQL queries, no conditional updates, no compound keys, and nothing fancy. 
Just plain simple storage (by default Expando stores only Name => Pickle, but you can change that -
see the reference documentation) with customizable basic validation. And yes we borrowed the name from the Google App Engine 
Expando object :)

Finally, by default, Expando keys are case-insensitive alpha-numeric strings which may have underscores in-between them 
(however they may not start with an underscore), while Expando values are any pickleable python object - for maximum flexibility. 
While, it is tempting to use Expando as a cache; we *strongly* advise you not to do so - we have designed and provided 
the cache API package as part of home for that purpose; use the right tool for
the right circumstance.

Here's how you use an Expando. For more details consult the reference documentation for home.

class Author(Expando):
    pass

author = Author()
author["name"] = "Sam Harris"                               # SINGLE SET
author["class"] = "99"                                      # SINGLE SET
author.save()                                               # SAVE IN BATCH
author.put({                                                # MULTI SET IN BATCH
    "name" : "Sam Harris",
    "address" : "#10 Downing Street, London",    
})
author.put("name", "Sam Harris", ttl=20)                       # SAVE WITH TTL
                                
found = Author.read(author.id)
name = found["name"]                                           # SINGLE GET
name, cls, address = found.get(["name", "class", "address"])   # MULTI GET
authors = Author.all()                                         # RETRIEVE ALL AUTHORS

"""
class Expando(BaseModel):
    '''A dynamically and infinitely expandable model'''
    
    def __new__(cls, *arguments, **keywords):
        '''Customizes all Model instances to include special attributes'''
        from cqlalchemy.core.commons import Name, Pickle
        if not hasattr(cls, "id"):
            cls.id = UUID()
        if not hasattr(cls, "default"):
            cls.default = Default(Name(), Pickle())
        if not hasattr(cls, "expire"):
            cls.expire = ExpiryProperty()
        instance = BaseModel.__new__(cls, *arguments, **keywords)
        return instance
    
    def __init__(self, **keywords):
        '''Basic initialization'''
        super(Expando, self).__init__()
        for name, value in list(keywords.items()):
            self[name] = value
        self.__saved__ = False
        #self.__table__ = ExpandoTable(self)
    
    @classmethod
    def create(cls, arguments={}, unique=False):
        '''Creates a new Expando, saves it and then returns it'''
        instance = cls()
        for name in arguments:
            instance[name] = arguments[name]
        instance.save(unique)
        return instance
        
    def saved(self):
        """
        Tells if this Expando has been saved to the data store before
        
        A Expando is deemed to have been saved if its keys hasn't
        changed since it was last persisted in Cassandra.
        """
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
    
    def get(self, properties=None, all=False):
        '''Reads multiple properties previously stored in this Expando from the datastore'''
        return self.__table__.get(properties, all)
        
    def put(self, name=None, value=None, ttl=None):
        '''Alternative set method, which allows multi-set and ttl values'''
        if isinstance(name, dict):
            return self.__table__.putmany(name, ttl)
        else:
            values = dict()
            values[name] = value
            return self.__table__.putmany(values, ttl)
    
    def save(self, unique=False):
        '''Stores this Expando to Apache Cassandra'''
        self.__table__.save(unique)
    
    @classmethod
    def upsert(cls, data):
        """
        Updates an already existing Expando instance in the datastore, avoid the 
        read-before-write anti-pattern. Returns None.
        """
        instance = cls(**data)
        instance.save()
            
    @classmethod
    def read(cls, id, properties=None):
        '''Read an expando from the data store'''
        found = ExpandoTable(cls).read(id, properties)
        return found
    
    @classmethod
    def delete(cls, *keys):
        """Deletes this Model from the data store"""
        ExpandoTable(cls).delete(*keys)
    
    @classmethod
    def truncate(cls):
        '''Truncates this Expando clearing away all its data'''
        ExpandoTable(cls).truncate()
    
    @classmethod
    def count(cls):
        '''Count how many instances of this kind exist in the datastore'''
        return ExpandoTable(cls).count()
        
    @classmethod
    def all(cls):
        '''Returns all the instances of this Expando stored in the Model'''
        return ExpandoTable(cls).all()
    
    def __str__(self):
        '''A String representation of this Model'''
        id = self.id if hasattr(self, "id") else None
        format = "[%s <Expando> => (id: %s)]" % (self.kind(), id)
        return format
    
    def __eq__(self, other):
        '''Checks if two Expando objects are equal'''
        if not type(other) == type(self):
            return False 
        us = getattr(self, "id", None)
        them = getattr(other, "id", None)
        return us == them
                  
"""    
Model: 
The basic unit of persistence for home, this is the recommended
way to go when you want to store clearly defined things to Cassandra. 

A Model is always aware of the changes you make to it; ergo models 
persist only changes you make to them; thereby saving bandwidth and 
unnecessary network connections to the datastore service. A Model also 
knows the best way to save changes made to it; it knows when to batch 
changes one update query, and when to execute updates/deletes in multiple 
sequential queries - either ways, It cleanly maps your object to Apache 
Cassandra consistently and performantly.

Models are very performat because they take advantage of Cassandra's
inbuilt caching/compresssion system, and they are very versatile to
use because they allow you to store properties (with support for all
sorts of interesting descriptors - see the home/core/commons module), 
index them, query for them, update them (including using conditional 
updates), and even control their TTL as a group.

Models also make the use of compound keys for your Model transparent
to you. Incase you didn't get it the first time, Models are the way to
go when you want to store clearly defined objects in Cassandra.

Model is designed to be used when you intend to store an object with
properties which you know before hand; on the other hand, you can inherit 
from Expando if you're unsure of your data model before hand 
(maybe during prototyping), or when you just want to store objects with alot 
of properties (Wide Rows).

Here is a simple Model

>>  class Profile(Model):
        name = String(indexed=True, required=True)
        gender = String(choices=('M', 'F',))

>>  person = Profile(name="Iroiso", gender='M')
>>  person.save()

"""
class Model(BaseModel):
    '''Unit of Persistence'''
    def __new__(cls, *arguments, **keywords):
        '''Customizes all Model instances to include special attributes'''
        instance = BaseModel.__new__(cls)
        if not hasattr(cls, "id"):
            cls.id = UUID()
        if not hasattr(cls, "expire"):
            cls.expire = ExpiryProperty()
        cls.objects = ObjectsProperty()
        cls.__fields__ = list(fields(cls, CqlProperty).items())
        cls.__keys__ = set()
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
        from home.core.types import TypedCollection
        self.validate()
        model = ModelTable(self) 
        if self.saved():
            model.update(when)
        else:
            model.new(unique)
        for name, property in self.__fields__:  #Commit the changes in all collections 
            if isinstance(property, CqlCollection):
                value = getattr(self, name, None)
                if isinstance(value, TypedCollection):
                    value.commit()
        self.differ.commit()  # Commit the differ for the model finally.
        self.__saved__ = True # Mark this model as saved.
    
    @classmethod
    def upsert(cls, data, when={}):
        """
        Updates an already existing model instance in the datastore, avoid the 
        read-before-write anti-pattern. Returns None.
        """
        instance = cls(**data)
        instance.save(when=when)
    
    def saved(self):
        """
        Tells if this Model has been saved before
        
        A Model is deemed to have been saved if its keys hasn't
        changed since it was last persisted in Cassandra.
        """
        if not self.__saved__:
            return False
        dirty = False
        for key in self.__keys__:
            if key in self.differ.changed():
                dirty = True
        return self.__saved__ and not dirty
                 
    @classmethod
    def read(cls, id):
        """Retreives objects from the data store"""
        found = ModelTable(cls).read(id)
        if found:
            found.__saved__ = True
            found.differ.commit()
        return found
        
    @classmethod
    def delete(cls, *keys):
        """Deletes this Model from the data store"""
        ModelTable(cls).delete(*keys)
    
    @classmethod
    def truncate(cls):
        '''Truncates this Model deleting all its data'''
        ModelTable(cls).truncate()
    
    @classmethod
    def query(cls, **keywords):
        '''Allows you to easily build queries on this Model'''
        return ModelTable(cls).query(**keywords)
        
    @classmethod
    def count(cls, **keywords):
        '''Counts all the instances of this Model from the data store'''
        return ModelTable(cls).count(**keywords)
    
    @classmethod
    def all(cls):
        '''Returns all the stored instances of the Model'''
        return ModelTable(cls).all()
    
    def __eq__(self, other):
        '''Two Models are equal if and only if their keys are equal'''
        if not isinstance(other, type(self)):
            return False
        eq = True
        for key in self.__keys__:
            if key in other:
                eq = self[key] == other[key]
        return eq
        
    def __str__(self):
        '''A String representation of this Model'''
        id = self.id if hasattr(self, "id") else None
        format = "[%s <Model> => (id: %s)]" % (self.kind(), id)
        return format


"""
Operator:
Represents comparison operators CQL queries that respects Models 
and descriptors; therefore making the entire usage experience 
intuitive.

So, given data models like this:

>>  class Author(Model):
        name = String(indexed=True)

>>  class Book(Model):
        name = String(indexed=True)
        price = Float(indexed=True)
        author = Reference(Author, indexed=True)
    
You can do queries like:

>>  book = Book.query(name=EQ("War and Peace"), price=GT(25.03)).one()

or use other other models as part of the query when you are querying against
and indexed Reference property.

>>  author = Author.query(name="Leo Tolstoy").one()
>>  book = Book.query(author=author).one() 
"""
class Operator(object):
    '''The Base Operator that all filters inherit from.'''
    def __init__(self, right):
        '''Every operator should atleast provide the LHS'''
        self.right = right
        
    def convert(self):
        '''Generic implementation for the conversion routine.'''
        if not bool(hasattr(self, "left") and hasattr(self, "model") and hasattr(self, "right")):
            raise BadValueError("This Operator isn't complete.")
        if not isinstance(self.left, str):
            raise BadValueError("The LHS of a EQ query has to be a valid property name")
        property = fields(self.model, CqlProperty).get(self.left, None)
        if not property:
            raise BadValueError("{self.left} is not a property".format(self=self))
        if property.name != "id" and not property.key and not property.indexed():
            raise BadValueError("Operands must be an id, clustering key or an indexed property")
        left = self.left
        right = property.convert(self.model, self.right) #Normal Conversion.
        return left, right
    
    def __str__(self):
        raise NotImplemented("Implemented in subclasses")

   
class EQ(Operator):
    "Represents the '=' operator in CQL"
    
    def __str__(self):
        """Implementation for the Model.query(name=EQ("Hello")) operand"""
        left, right = self.convert()
        return "{left} = {right}".format(left=left, right=right)


class LT(Operator):
    "Represents the '<' CQL Operator"
    
    def __str__(self):
        "Implementation for the Model.query(price=LT(20))"
        left, right = self.convert()
        return "{left} < {right}".format(left=left, right=right)


class GT(Operator):
    "Represents the '>' CQL operation"
    
    def __str__(self):
        "Implementation for the Model.query(price=GT(10))"
        left, right = self.convert()
        return "{left} > {right}".format(left=left, right=right)


class LTE(Operator):
    "Represents the '<=' operator in CQL"
    
    def __str__(self):
        '''Implementation for the Model.query(price=LTE(25)) operand'''
        left, right = self.convert()
        return "{left} <= {right}".format(left=left, right=right)


class GTE(Operator):
    "Represents the '>=' operator in CQL"
    
    def __str__(self):
        '''Implementation for the Model.query(name=GTE(10))'''
        left, right = self.convert()
        return "{left} >= {right}".format(left=left, right=right)


class IN(Operator):
    "Represents the 'IN' operator in CQL"
    
    def __init__(self, *right):
        '''Every operator should atleast provide the LHS'''
        self.right = right
    
    def convert(self):
        '''Converts all the items in the IN operator'''
        if not bool(hasattr(self, "left") and hasattr(self, "model") and hasattr(self, "right")):
            raise BadValueError("This Operator isn't complete.")
        if not isinstance(self.left, str):
            raise BadValueError("The LHS of a EQ query has to be a valid property name")
        property = fields(self.model, CqlProperty).get(self.left, None)
        if not property:
            raise BadValueError("{self.left} is not an indexed property".format(self=self))
        if property.name != "id" and not property.key and not property.indexed():
            raise BadValueError("Operands must be an id, clustering key or an indexed property")
        left = self.left
        converted = []
        for value in self.right:
            v = property.convert(self.model, value)
            converted.append(v)
        return left, converted
        
    def __str__(self):
        '''Implementation for the Model.query(name=IN(1,2,3))'''
        left, right = self.convert()
        right = ", ".join(right)
        return "{left} IN ({right})".format(left=left, right=right)

       