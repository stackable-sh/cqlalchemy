import uuid
import inspect
import itertools
from enum import Enum
from copy import deepcopy
from collections import OrderedDict
from typing import Union, List, Iterable

import schema

from cqlalchemy.options import keyspace
from cqlalchemy.core.builtins import object, json, fields, assertType
from cqlalchemy.core.serialization import quote
from cqlalchemy.core.differ import EntityTracker, Action


__all__ = [
    "Model",
    "Expando",
    "Vector",
    "Block",
    "Table",
    "UUID",
    "Reference",
    "Counter",
    "Key",
    "Pointer",
]

READWRITE, READONLY = 1, 2
Index = Enum("Index", ["ALL", "KEYS", "VALUES"])
RESERVED = {"when", "unique", "version", "keyspace", "predicate", "ttl", "batch"}


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
    """The contract for all converters"""

    def __call__(self, value):
        """A shortcut to validate"""
        return self.validate(value)

    def validate(self, value):
        """Basic Definition just returns the value passed to it"""
        return value

    def convert(self, instance, value):
        """Convert the object to the C* representation for it"""
        raise NotImplementedError("Implemented in subclasses")

    def deconvert(self, value):
        """Converts a @value from the C* to python object."""
        raise NotImplementedError("Implemented in subclasses")

    def saveable(self):
        """All descriptors can be saved by default"""
        raise NotImplementedError("Implemented in subclasses")

    def serialize(self, value):
        """Transforms the value in this converter into something displayable in JSON"""
        raise NotImplementedError("Implemented in subclasses")

    def deserialize(self, value):
        """Transforms a 'potentially unsafe' value from JSON into something suitable for python"""
        raise NotImplementedError("Implemented in subclasses")


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
                if isinstance(instance, Entity):  # Track Change for Entity
                    operation = instance.__tracker__.op(
                        code=Action.OSET, parent=instance, name=self.name, value=value
                    )
                    instance.__tracker__.track(operation)
            self.deleted = False
        else:
            raise AttributeError("Cannot find %s in  %s " % (self, instance))

    def __get__(self, instance, owner):
        """Read the value of this property"""
        # We do not support class descriptors in cqlalchemy.
        if self.name is None:
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
                    raise AttributeError("Cannot find %s in %s" % (self, instance))
        else:
            raise AttributeError(
                "Cannot find any property named %s in: %s" % (self.name, owner)
            )

    def __delete__(self, instance):
        """Delete this Property from @instance"""
        if self.deleted:
            return
        if self.mode != READWRITE:
            raise AttributeError("This is NOT a READWRITE Property, Error")
        if self.name is None:
            name = Property.search(instance, None, self)
            self.configure(name, instance)
        if self.name is not None:
            try:
                del instance.__dict__[self.name]
                if hasattr(instance, "__store__"):
                    del instance.__store__[self.name]
                    if isinstance(instance, Entity):  # Track Delete for Entity
                        operation = instance.__tracker__.op(
                            code=Action.ODELETE, parent=instance, name=self.name
                        )
                        instance.__tracker__.track(operation)
                self.deleted = True
            except (AttributeError, KeyError) as error:
                raise error
        else:
            raise AttributeError(
                "Cannot find Property: %s in: %s or its ancestors" % (self, instance)
            )

    @staticmethod
    def search(instance, owner, descriptor):
        """Returns the name of this descriptor by searching its class hierachy"""
        """Search class dictionary first"""
        if instance is not None:
            for name, value in list(instance.__class__.__dict__.items()):
                if value is descriptor:
                    return name
            """Then search all the ancestors dictionary"""
            for cls in type(instance).__bases__:
                for name, value in list(cls.__dict__.items()):
                    if value is descriptor:
                        return name
        elif owner is not None:
            for name, value in list(owner.__dict__.items()):
                if value is descriptor:
                    return name
            """Then search all the ancestors dictionary"""
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
            raise BadValueError(
                "Property: %s is required, it cannot be empty" % self.name
            )
        if self.choices:
            if value not in self.choices:
                raise BadValueError(
                    "The property %s is %r; it must be on of %r"
                    % (self.name, value, self.choices)
                )
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
        """String representation of a Property"""
        return "{self.__class__}: {self.name}".format(self=self)


"""
CqlProperty:
Represent a property that can be converted to CQL and persisted to cassandra.
As a distinction, all CqlProperty objects expect an optional 'key', and 'indexed'
property which allow you to create compound/clustering keys and allow indexing.
"""


class CqlProperty(Property):
    """A Property object that can be stored and queried in cassandra using CQL"""

    type, ctype = None, None

    def __init__(self, **keywords):
        """Calls the super constructor, and adds the ability to make properties keys"""
        super(CqlProperty, self).__init__(**keywords)

        self.key = keywords.pop("key", False)
        self.primary = keywords.pop("primary", False)
        self.index = keywords.pop("index", False)
        self.static = keywords.pop("static", False)
        self.ttl = keywords.pop("ttl", None)
        self.composite = keywords.pop("composite", [])

        if self.primary:
            self.key = True
        if self.key:
            self.required = True
        if self.key and not self.primary:
            order = keywords.get("order", None)  # Make sure
            if order and order.upper() not in ("ASC", "DESC"):
                raise BadValueError("`order` must be either `ASC` or `DESC`")
            self.order = order.upper() if order else None

    def validate(self, value):
        """Asserts that the value provided is compatible with this property"""
        if self.key and self.empty(value):
            raise BadValueError(
                "Property: %s is a key; hence its required, it cannot be empty"
                % self.name
            )
        return super(CqlProperty, self).validate(value)

    def indexed(self):
        """Checks if this property should be indexed"""
        if not self.saveable():
            return False
        return self.index

    def saveable(self):
        return True


"""
Collection:
Abstracts the basic, and required behaviour for all Collection objects related to C* 
"""


class Collection(CqlProperty):
    """Base object for List<T>, Map<T, V>, and Tuple<T,V>."""

    def __init__(self, **keywords):
        """Basic initialization for Collection objects"""
        if "key" in keywords:
            raise BadValueError(
                "Collection objects cannot be used as primary or partition keys"
            )
        if "choices" in keywords:
            raise BadValueError(
                "Collection objects do not support the `choices` keyword parameter"
            )
        index = keywords.get("index", False)
        assertType(
            index,
            (bool, Index),
            "You have to provide either a `bool` or an instance of `Index`",
        )
        if index is True:
            self.index = Index.ALL
        super(Collection, self).__init__(**keywords)

    def __set__(self, instance, value):
        """Prevents users from overwriting this variable with new data"""
        if self.name is None:
            raise AttributeError(
                "This descriptor doesn't exist with {instance}".format(
                    instance=instance
                )
            )
        found = getattr(instance, self.name)
        if found:
            raise AttributeError(
                "You should not explicitly overwrite an existing List<T>, Map<K,V> or Tuple<T>"
            )
        else:
            super(Collection, self).__set__(instance, value)


"""
UnSaveable:
The base class of all descriptors that cannot be saved.
"""


class UnSaveable(Property):
    """A Property that cannot be persisted"""

    def saveable(self):
        """All unsaveable descriptors cannot be saved"""
        return False


"""
UnIndexable:
The base class of all Properties that cannot be indexed. 
"""


class UnIndexable(CqlProperty):
    """A Property that cannot be indexed"""

    def indexed(self):
        """An un-indexable property cannot be indexed"""
        return False


"""
Type:
A Descriptor that provides CQL aware type coercion, checking and validation. 
"""


class Type(CqlProperty):
    """Does type checking and coercion"""

    def __init__(self, **keywords):
        self.type = (
            keywords.pop("type", None) if self.type is None else self.type
        )  # LEAVE OLDER TYPES
        super(Type, self).__init__(**keywords)

    def __call__(self, value):
        """A shortcut to self.validate(value)"""
        return self.validate(value)

    def validate(self, value):
        """Add type checking and coercion and automatic construction to basic validation"""
        value = super(Type, self).validate(value)
        if self.type is None:
            return value
        if value is not None and not isinstance(value, self.type):
            try:
                if isinstance(value, list) or isinstance(value, tuple):
                    value = self.type(*value)
                elif isinstance(value, dict):
                    value = self.type(**value)
                else:
                    value = self.type(value)
            except Exception as e:
                raise BadValueError("Failed to Coerce: %s to %s" % (value, self.type))
        return value


"""
Basic:
Represents a type that you can convert, serialize with the str builtin function.
We allow for the deconvert function to be implemented by the subclass.
"""


class Basic(Type):
    """A Type that can be converted with str"""

    type, ctype = str, "text"

    def deconvert(self, value):
        """Changes from C* type to our native python type"""
        if isinstance(value, self.type):
            return value
        else:
            return self.type(value)

    def convert(self, instance=None, value=None):
        """Converts from native python to C* type"""
        value = self.validate(value)
        if value is None:
            raise BadValueError(
                "We cannot convert 'None' to a native type for property: %s" % self.name
            )
        if isinstance(value, str):
            return quote(value)
        if isinstance(value, bool):
            value = "true" if value else "false"
            return value
        val = self.type(value)
        return str(val)


"""
ExpiryProperty:
The Expiry property for Model objects.
"""


class ExpiryProperty(UnSaveable):
    """An unsaveable descriptor that allows you to make a model expire"""

    def __get__(self, instance, owner):
        """Returns the set expiry value or the default one"""
        result = super().__get__(instance, owner)
        if not result:
            return owner.__options__.get("expire", 0)
        else:
            return result

    def validate(self, value):
        """You can only set positive integers/longs here"""
        if not isinstance(value, int):
            try:
                value = int(value)
                return value
            except Exception:
                raise BadValueError(
                    "You can only set values that can be converted to numbers here."
                )
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

book = Book.objects.where(name="War & Peace").get()
assert book.owner.name == "Cody Gakpo"

# Find book by author index.
books = Book.objects.where(author=person).all()
```
"""


class Reference(Basic):
    """Descriptor that saves a Pointer to another Entity in C*"""

    def __init__(self, table, **keywords):
        """Create a Reference object"""
        from cqlalchemy.connection.table import Schema

        if not issubclass(table, (str, Entity)):
            raise BadValueError(
                "Reference only supports Entity objects, or their ordinary Table names"
            )
        table = table if inspect.isclass(table) else Schema.get(table)
        if not table:
            raise BadValueError(f"We could not find any Entity classes for {table}")
        self.table = table
        super(Reference, self).__init__(**keywords)

    def convert(self, instance=None, value=None):
        """Converts an Entity to a Pointer"""
        if value is None:
            return None
        elif isinstance(value, Entity):
            value = self.validate(value)
            pointer = Pointer.create(value)
            return pointer.convert()
        elif isinstance(value, Pointer):
            value = self.validate(value)
            return pointer.convert()
        else:
            raise BadValueError("We can only convert Entity objects to Pointer")

    def deconvert(self, value):
        """Converts a Pointer to an Entity"""
        try:
            if value:
                slug = json.loads(value)
                slug = Pointer.schema.validate(slug)
                if slug["keyspace"] == self.table.keyspace():
                    pointer = Pointer(slug["table"], **slug["key"])
                    return pointer.get()
                else:
                    raise BadValueError(
                        "Keyspace on the Pointer and your Entity do not match"
                    )
            else:
                return None
        except Exception as e:
            raise e

    def validate(self, value):
        """Makes sure you can only set a Model that is complete on a Reference"""
        if self.empty(value):
            return None
        if not isinstance(value, (self.table, Pointer)):
            raise BadValueError(
                "Value: {0} must be an instance of {1}".format(value, self.table)
            )
        if isinstance(value, self.table):
            value.validate()  # Finally validate the model then return it.
            return value
        if isinstance(value, Pointer):
            if value.table != self.table.table():
                raise BadValueError(f"Provide a Pointer to a {self.table} entity")
            return value

    def __eq__(self, other):
        """Two Reference objects are equal if they contain a pointer to the same class"""
        if not type(self) == type(other):
            return False
        return other.table == self.table

    def __hash__(self):
        key = (
            self.__class__,
            self.table,
        )
        return hash(key)

    def __str__(self):
        """Returns a str representation of this Reference"""
        return str(self)


"""
ObjectsProperty:
Allows you to build queries fluently with a Model. It automatically creates a new query object
whenever its descriptor is accessed.
"""


class ObjectsProperty(UnSaveable):
    """Allows us to automatically create new Builder objects."""

    def __get__(self, instance, owner):
        """Everytime objects is accessed create a new Builder instance"""
        from cqlalchemy.connection.cql import Builder, CollectionBuilder

        if issubclass(owner, (Expando, Vector, Block)):
            return CollectionBuilder(owner)
        elif issubclass(owner, Model):
            return Builder(owner)
        else:
            raise BadValueError(
                "We only support `objects` property on Model, Expando, Vector and Block"
            )


"""
HistoryProperty:

We provide *infinite* version control for your Entity objects (which you can configure 
on a per class basis). HistoryProperty fetches (lazily) the history of changes to its
parent and returns it for your use - giving you `point in time restore` without any 
other work on your part

```python
import arrow

class Profile(Model, version=True):
    name = String(index=True, required=True)
    gender = String(choices=('M', 'F',))

person = Profile.create(name="Jordan Lopez", gender='M')           # Create v1.0 of the object
person.name = "Jennifer Watson"                                    # Change the object, and save it to create a v2.0 
person.gender = 'F'
person.save()

previous = person.history[0]                               # Fetch the most recent change from the history property. 
print(previous["name"])                                    # You can access the state of the object as it was at v1.0
previous.revert()                                          # Reverts the state of the object to the state at v1.0, creating v3.0

assert person.name == 'Jordan Lopez'
assert person.gender == 'M'

print(person.history.last())                               # Returns the latest version of the object
print(person.history.first())                              # Returns the first version

timestamp = arrow.now().shift(hours=-24)
change = person.history.at(timestamp)                      # Returns the most recent change before `timestamp`
batch = change.batch 
print(change)

now = arrow.now()
start, end = now.date(), now.shift(days=-30)
                            
for change in person.history.span(start=start, end=end):   # To see changes over a particular period of time use `span`
    print(change)

history = History([instance, ])                              
timestamp = arrow.now().shift(days=-45)
history.restore(to=timestamp)                               #  Rewind a group of objects/relations to `timestamp`
history.restore(to=batch)                                   #  Rewind all the changes in affected entities to state as of `batch`
```

You can learn more by looking at the official documentation for the `versioning` package
to learn how to handle related objects, and reverting changes in objects in the same 
batch operation.

"""


class HistoryProperty(UnSaveable):
    """A proxy that allows you to fetch versioned changes to this object"""

    def __get__(self, instance, owner):
        """Everytime objects is accessed create a new Builder instance"""
        from cqlalchemy.history import History
        return History(instance)


"""
UUID:
Generates Type 4 UUIDs on the fly when they are requested for; this is
useful for creating UUID's for Models.
"""


class UUID(Type):
    """A type 4 UUID Property"""

    type, ctype = str, "uuid"

    def __init__(self, **keywords):
        """Simply makes sure that a UUID Property is READWRITE"""
        super(UUID, self).__init__(**keywords)

    def validate(self, value):
        """Validates UUID objects."""
        try:
            if value is None:
                return uuid.uuid4()
            if isinstance(value, uuid.UUID):
                return value
            coerced = None
            try:
                coerced = uuid.UUID(value)
            except Exception as e:
                coerced = uuid.UUID(bytes=value)

            if coerced:
                return coerced
            else:
                raise BadValueError("Could not convert %s to a UUID" % value)
        except Exception as e:
            raise BadValueError("Could not convert %s to a UUID" % value)

    def __get__(self, instance, owner):
        """Read the value of this property"""
        if self.name is None:
            self.name = UUID.search(instance, owner, self)
        if self.name is not None:
            try:
                value = None
                if instance is not None:
                    value = instance.__dict__.get(self.name, None)
                elif instance is None and owner is not None:
                    value = owner.__dict__.get(self.name, None)
                else:
                    raise ValueError("`instance` and `owner` can't be None")
                if value is None:
                    value = uuid.uuid4()
                    self.__set__(instance, value)
                return value
            except (AttributeError, KeyError) as error:
                raise error
        else:
            raise AttributeError(
                "Cannot find any property named %s in: %s" % (self.name, owner)
            )

    def deconvert(self, value):
        """Convert the UUID bytes to a python object"""
        if value is None:
            return None
        elif isinstance(value, uuid.UUID):
            return value
        else:
            return uuid.UUID(value)

    def convert(self, instance=None, value=None):
        """Converts the basic type with the str operation, which we can do an eval() on."""
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
Entity:
Entity is the super class of all objects that can be saved into C*.
We implement the dict protocol, and other basic functionality that is shared across the board here. 
"""


class Entity(object):
    """The objects that all Models inherit"""

    def __init_subclass__(cls, keyspace=None, expire=0, batch=True, version=False, **keywords):
        """Initializes meta variables for Entity objects"""
        from cqlalchemy.connection.table import Schema

        super().__init_subclass__(**keywords)
        cls.__options__ = {}
        cls.__options__["keyspace"] = keyspace
        cls.__options__["expire"] = expire
        cls.__options__["version"] = version
        cls.__options__["batch"] = batch
        cls.expire = ExpiryProperty()
        if version:
            cls.history = HistoryProperty()
        Schema.put(cls)  # Register the class with the Schema Registrar

    def saved(self):
        """Returns True if this object has been saved at least once, and its keys have not changed."""
        raise NotImplementedError("Implemented in subclasses.")

    @classmethod
    def table(cls):
        """The table name of this class."""
        return cls.__name__.lower()

    @classmethod
    def keyspace(cls):
        """ "Returns the keyspace of this Table, falling back on the configured option"""
        found = cls.__options__.get("keyspace", None)
        if found:
            return found.lower()
        return keyspace()


"""
Table

A shorthand for creating `Expando, Vector, and Block` Entity classes.

```python
Author = Table("Author", Expando, keyspace="Kindle", expire=days(30))

# Is syntatically equivalent to => 

class Author(Expando, keyspace="Kindle", expire=days(30)):
    pass 

```
"""


def Table(name, parent, keyspace=None, expire=0, batch=True, version=False):
    if not issubclass(parent, (Expando, Vector, Block)):
        raise BadValueError(
            "You may also use the `Table` shorthand for `Expando, Vector or Block`"
        )
    kind = type(name, (parent,), {}, keyspace=keyspace, expire=expire, version=version)
    return kind


"""
options

A shortcut for accessing pre-configured entity class options

```python
class Book(Expando, version=True):
    pass 
    
version = options(Book, "version")
```
"""


def options(entity: Entity, name: str, default=None):
    """Returns configured options for name(s) from the entity"""
    return entity.__options__.get(name, default)


"""
Key

A simple, consistent, and `order aware` abstraction over all the key(s) in any Entity n C*. 
`Key` objects are used internally to help with the discovery, and behavioral enforcement 
of the 'key' attribute requirements of a C* Entity. 

This is how to use a Key object.

```python
from cqlalchemy import Expando, Key
from cqlalchemy.time import days

Author = Table("Author", Expando, keyspace="Kindle", expire=days(30))

# Create a Key abstraction for the Author Entity

key = Key.create(Author)
assert "id" in key.parts
assert "Kindle" == key.keyspace
assert "id" == key.primary
```
"""


class Key(object):
    """An abstraction over the partition & clustering key attributes of an Entity"""

    def __init__(
        self,
        keyspace: str = None,
        table: str = None,
        primary: Union[str, list] = None,
        others: List[str] = [],
    ):
        """Creates a new Key"""
        self.keyspace = keyspace
        self.table = table
        self.others = others
        self.composite = []
        if primary and isinstance(primary, str):
            self.primary = primary
            self.composite = []
        elif primary and isinstance(primary, list):
            self.primary = primary[0]
            self.composite = primary
        else:
            self.primary = None
            self.composite = []

    @property
    def parts(self):
        """Returns all of the parts of this Key, preserving natural order"""
        keys = []
        if not self.composite:
            keys.append(self.primary)
            keys.extend(self.others)
        else:
            keys.extend(itertools.chain(self.composite, self.others))

        output, bag = [], set()
        for part in keys:
            # Add the keys to the output, while preserving their natural order
            if part not in bag:
                output.append(part)
                bag.add(part)
        return output

    @property
    def partition(self):
        """Returns partition keys whether singular or composite"""
        result = []
        if self.composite:
            result.extend(self.composite)
        else:
            result.append(self.primary)

        output, bag = [], set()
        for part in result:
            # Add the keys to the output, while preserving their natural order
            if part not in bag:
                output.append(part)
                bag.add(part)
        return output

    @property
    def cluster(self):
        """Returns clustering keys if they exist"""
        results = [name for name in self.parts if name not in self.partition]
        return results

    def contains(self, name):
        """Checks if @name is part of this Key"""
        return name in self.parts

    @classmethod
    def create(self, entity: Entity):
        """Finds and creates a Key object from the Table"""
        if inspect.isclass(entity):
            if not issubclass(entity, Entity):
                raise ValueError(
                    "You may only create Key objects for subclasses of Entity"
                )
        else:
            if not isinstance(entity, Entity):
                raise ValueError(
                    "You may only create Key objects for subclasses of Entity"
                )
            entity = entity.__class__

        table = entity.table()
        keyspace = entity.keyspace()
        primary = None
        composite = []
        others = []

        attributes = fields(entity, CqlProperty)
        properties, primary = [], []

        for name, property in attributes.items():
            if property.key:
                properties.append(name)
            if property.primary:
                primary.append(name)

        if len(primary) > 1:
            raise BadValueError(
                "You may not have more than one `primary` key defined in the Entity"
            )
        if len(properties) == 0:
            raise BadValueError("You must have one `key` defined in your Entity")

        if primary:
            primary = primary[0]
            properties.remove(primary)
            attribute = attributes.get(primary)
            if attribute.composite:
                # Add the primary key it to the list of primary keys
                extensions = []
                extensions.append(primary)
                if isinstance(attribute.composite, (list, set)):
                    extensions.extend(attribute.composite)
                if isinstance(attribute.composite, str):
                    extensions.append(attribute.composite)
                for name in extensions:
                    property = attributes.get(name, None)
                    if property and property.key:
                        composite.append(name)
                    else:
                        raise BadValueError(
                            "Your `composite` must be one of the `key` objects in the Entity"
                        )
        else:
            if len(properties) == 1:
                primary = properties[0]
            else:
                raise BadValueError(
                    "You must have one `primary` key defined in your Entity"
                )
        if properties:
            others = properties

        primary = composite if composite else primary
        instance = Key(keyspace=keyspace, table=table, primary=primary, others=others)
        return instance

    def __repr__(self):
        """Returns a str that we can instantiate with an eval in to a `Key`"""
        if self.composite:
            return f"Key(keyspace='{self.keyspace}', table='{self.table}', primary='{self.composite}', others={repr(self.others)})"
        else:
            return f"Key(keyspace='{self.keyspace}', table='{self.table}', primary='{self.primary}', others={repr(self.others)})"

    def __eq__(self, other):
        if not isinstance(other, Key):
            return False
        else:
            return (
                self.keyspace == other.keyspace
                and self.table == other.table
                and self.parts == other.parts
            )

    def __str__(self):
        return repr(self)


"""
Pointer

A Pointer to an Entity persisted in C*.  
Pointer is designed to be used in conjunction with `Key` and `Reference`

```python
from datetime import datetime
from cqlalchemy import Expando, Pointer, Reference
from cqlalchemy import String, UUID, Reference, DateTime

Author = Expando("Author", keyspace="Kindle")
author = Author.create(name="Sam Harris", age=49, category="Philosophy")

# Create a Pointer to the `author` object that is already persisted

pointer = Pointer.create(author)  
assert pointer.key is not None
assert pointer.keyspace == "Kindle"
assert pointer.table == "Author"
assert pointer.primary == author["id"]
id = author["id"]

class Book(Entity):
    id = UUID(primary=True, composite=["isbn",]))
    isbn = String(key=True)
    name = String(required=True, index=True)
    author = Reference(Author, index=True, required=True)
    created = DateTime(required=True, index=True)

new = Book.create(
    id ="98e50d75-d025-4d4d-b99f-e08024ac44ec",
    isbn="978-3-16-148410-0", 
    name="Age of Scientism",
    author=author, 
    created=datetime.now()
)

# Create a Pointer, check for its validity, and fetch the connected object

pointer = Pointer('Book', id='98e50d75-d025-4d4d-b99f-e08024ac44ec', isbn='978-3-16-148410-0')
book = pointer.get()
assert isinstance(book, Book)
assert new == book
```
"""


class Pointer(object):
    """A Pointer to a persisted Entity in C*"""

    schema = schema.Schema({"keyspace": str, "table": str, "key": dict})

    def __init__(self, table: str, **keywords):
        """Creates a Pointer object"""
        from cqlalchemy.connection.table import Schema

        found = Schema.get(table)
        if not found:
            raise BadValueError(f"No Entity named `{table}` in the registry")
        
        table = found
        self.keyspace = table.keyspace()
        self.kind = table
        self.table = table.table()
        self.key = Key.create(table)
        self.entity = None
        self._parts_ = OrderedDict()

        for name in self.key.parts:
            if name not in keywords:
                raise BadValueError(f"{name} is a required `key` for your Entity")
            self._parts_[name] = keywords.get(name)

    @property
    def parts(self):
        return self._parts_

    @classmethod
    def create(self, entity: Entity):
        """Creates a Pointer object"""
        if not isinstance(entity, Entity):
            raise BadValueError("Provide a valid `Entity` instance to a create Pointer")
        parts = {}
        key = Key.create(entity.__class__)
        for name in key.parts:
            parts[name] = getattr(entity, name)
        pointer = Pointer(entity.table(), **parts)
        pointer.entity = entity
        return pointer

    def get(self):
        """Returns the connected Entity, fetching it from C* if necessary"""
        from cqlalchemy.connection.table import Schema

        if self.entity:
            return self.entity
        Entity = Schema.get(self.table)
        self.entity = Entity.objects.where(**self.parts).get()
        return self.entity

    def convert(self):
        """Converts to the C* compatible representation of Pointer"""
        marshal = {"keyspace": self.keyspace, "table": self.table, "key": self.parts}
        return quote(json.dumps(marshal))

    def __repr__(self):
        return f"Pointer('{self.table.title()}', {repr(self.parts)})"

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        if not isinstance(other, Pointer):
            return False
        else:
            return (
                self.keyspace == other.keyspace
                and self.table == other.table
                and self.parts == other.parts
            )


"""    
Model: 

This is the basic unit of persistence for cqlalchemy. We recommend the use of Model when 
you want to store clearly defined things to Cassandra. 

A Model is always aware of the changes you make to it; ergo models persist only changes you make to them; 
thereby saving bandwidth and unnecessary network connections to the datastore service. A Model also 
knows the best way to save changes made to it; it knows when to batch changes in one update query, and when to 
execute updates/deletes in multiple sequential queries - either ways, It cleanly maps your object to Apache 
Cassandra consistently and performantly.

Models are very performat because they take advantage of Cassandra's inbuilt caching/compresssion system, 
and they are very versatile to use because they allow you to store properties (with support for all sorts of 
interesting descriptors - see the cqlalchemy/core/commons module), index them, query for them, update them 
(including using conditional updates), and even control their TTL as a group (and individually).
Models also make the use of compound keys for your Model transparent to you. 

Model is designed to be used when you intend to store an object with properties which you know before hand; 
on the other hand, you can inherit from Expando if you're unsure of your data model before hand 
(maybe during prototyping), or when you just want to store objects with alot of properties (Wide Rows).

Here is a simple Model

```python

class Profile(Model):
    name = String(index=True, required=True)
    gender = String(choices=('M', 'F',))

person = Profile.create(name="Steve Jobs", gender='M')
```
"""


class Model(Entity):
    """Unit of Persistence"""

    def __new__(cls, *arguments, **keywords):
        """Customizes all Model instances to include special attributes"""
        from cqlalchemy.connection.table import Table

        cls.__properties__ = fields(cls, Property)
        cls.__fields__ = fields(cls, CqlProperty)
        keys, static = set(), set()
        for name, property in cls.__fields__.items():
            property.configure(name, cls)
            if name.startswith("_"):
                raise BadValueError(
                    "An Entity attributes cannot begin with an underscore"
                )
            if not name.islower():
                raise BadValueError("Entity attribute names must be lower case")
            if name in RESERVED:
                raise BadValueError(f"Entity attribute `{name}` is a reserved name")
            if property.ctype == "counter":
                raise BadValueError(
                    f"You cannot have `Counter` descriptors in `Model` use `CounterModel`"
                )
            if hasattr(property, "key") and property.key:
                keys.add(name)
            if hasattr(property, "static") and property.static:
                static.add(name)
        # If there is no defined key, create a default primary key for the Entity.
        if not keys:
            cls.id = UUID(primary=True)

        version = options(cls, "version", False)
        batch = options(cls, "batch", True)
        cls.objects = ObjectsProperty()
        cls.__table__ = Table(cls, batch=batch, version=version)
        cls.__key__ = Key.create(cls)
        if static and not cls.__key__.cluster:
            raise BadValueError(
                "You must have atleast one clustering key to use static columns"
            )

        # Connect the Change Data Capture Mechanism.
        instance = super().__new__(cls)
        instance.__store__ = {}
        instance.__pointer__ = None
        instance.__saved__ = False
        instance.__tracker__ = EntityTracker(
            instance, exclude=["__tracker__", "expire", "history"]
        )
        return instance

    def __init__(self, **keywords):
        """Creates an instance of this Model"""
        super().__init__()
        for name, value in keywords.items():
            setattr(self, name, value)

    def validate(self):
        """Checks if a Model can be persisted to C*"""
        from cqlalchemy.connection.table import Schema

        if not Schema.get(self.table()):
            Schema.put(self.__class__)

        for name, prop in self.__fields__.items():
            if hasattr(prop, "required") and prop.required:
                value = getattr(self, name, None)
                if prop.empty(value):
                    raise BadValueError("Property: %s is required" % name)
            elif hasattr(prop, "key") and prop.key:
                value = getattr(self, name)
                if prop.empty(value):
                    raise BadValueError(
                        "Property: %s is a key so it is required" % name
                    )
        if not self.__pointer__:
            self.__pointer__ = Pointer.create(self)

    def save(self, unique=False):
        """Stores this Model in Cassandra in one batch update."""
        self.validate()
        if self.saved():
            self.__table__.update(self)
        else:
            self.__table__.insert(self, unique)
        self.__saved__ = True  # Mark this model as saved.

    def set(self, name, value, predicate=None, ttl=0):
        """Add attribute persistence options on a per-column basis, during the execution of 'save'"""
        if not self.saved():
            raise ValueError("Save your Entity before using conditional updates")
        if name in self.__properties__:
            if name in self.__key__.parts:
                raise ValueError(
                    "You cannot use conditional updates or set TTL on `key` attributes"
                )
            setattr(self, name, value)
            operation = self.__tracker__.op(
                code=Action.OSET, parent=self, name=name, value=value
            )
            operation.conditions(predicate=predicate, ttl=ttl)
            self.__tracker__.track(operation)
        else:
            raise AttributeError(
                "You can only use conditional updates on defined properties"
            )

    def remove(self, name, predicate=None):
        """Modify attribute deletion options on a per-column basis, during the execution of 'save'"""
        if not self.saved():
            raise ValueError("Save your Entity before using conditional deletes")
        if name in self.__properties__:
            if name in self.__key__.parts:
                raise ValueError(
                    "You cannot use conditional deletes on `key` attributes"
                )
            delattr(self, name)
            operation = self.__tracker__.op(code=Action.ODELETE, parent=self, name=name)
            operation.conditions(predicate=predicate)
            self.__tracker__.track(operation)
        else:
            raise AttributeError(
                "You can only use conditional deletes on defined properties"
            )

    def saved(self):
        """Returns True if this model has been saved before, and its keys have not changed since then."""
        if not self.__saved__:
            return False

        self.validate()
        # Create a new disposable Pointer to check for change in the Entity keys.
        new = Pointer.create(self)  
        if new == self.__pointer__ and self.__saved__:  # The key has not changed,
            return True
        else:
            return False

    @property
    def key(self):
        """Returns the Pointer for this Entity"""
        return self.__pointer__

    @classmethod
    def create(self, **arguments):
        """Creates a new Model, saves it and then returns it"""
        unique = arguments.pop("unique", False)
        instance = self()
        for name in arguments:
            instance[name] = arguments[name]
        instance.save(unique=unique)
        return instance

    @classmethod
    def upsert(self, **arguments):
        """Updates an already existing model instance in the datastore, without the read-before-write anti-pattern"""
        predicate = arguments.pop("predicate", None)
        exists = arguments.pop("exists", True)

        instance = self()
        for name in arguments:
            instance[name] = arguments[name]
        instance.validate()
        if predicate:
            exists = False
            predicate.entity = instance
        self.__table__.upsert(instance, predicate=predicate, exists=exists)
        return instance

    @classmethod
    def read(self, key: Union[Pointer, dict]):
        """Fetches the Entity identified by @key from C*"""
        pointer = None
        if not isinstance(key, (Pointer, dict)):
            if len(self.__key__.parts) == 1:
                name = list(self.__key__.parts)[0]
                arguments = dict()
                arguments[name] = key
                pointer = Pointer(self.table(), **arguments)
            else:
                raise BadValueError(
                    "You have more than one `key` attribute defined in your Entity"
                )
        elif isinstance(key, Pointer):
            pointer = key
        else:
            pointer = Pointer(self.table(), **key)
        found = self.__table__.read(pointer)
        if found:
            found.__saved__ = True
            found.validate()
        return found

    @classmethod
    def refresh(self, instance: Entity):
        """Reloads @instance with the latest data from C*"""
        if not instance.saved():
            raise ValueError("You can only refresh a saved Entity")
        instance.validate()
        new = self.read(instance.key)
        return new

    @classmethod
    def delete(self, key: Union[Pointer, dict]):
        """Deletes the Entity identified by @key from C*"""
        pointer = None
        if not isinstance(key, (Pointer, dict)):
            if len(self.__key__.parts) == 1:
                name = list(self.__key__.parts)[0]
                arguments = dict()
                arguments[name] = key
                pointer = Pointer(self.table(), **arguments)
            else:
                raise BadValueError(
                    "You have more than one `key` attribute defined in your Entity"
                )
        elif isinstance(key, Pointer):
            pointer = key
        else:
            pointer = Pointer(self.table(), **key)
        self.__table__.delete(pointer)

    def __setitem__(self, key, value):
        """Implements dict protocol for adding attributes"""
        if key in self.__properties__:
            setattr(self, key, value)
        else:
            raise AttributeError("There is no descriptor for this attribute")

    def __getitem__(self, key):
        """Implements dict protocol for getting attributes"""
        if key in self.__properties__:
            return getattr(self, key)
        else:
            raise AttributeError("There is no descriptor for this attribute")

    def __delitem__(self, key):
        """Implements dict protocol for removing attributes"""
        if key in self.__properties__:
            delattr(self, key)
        else:
            raise AttributeError("There is no descriptor for this attribute")

    def __contains__(self, key):
        """Implements dict protocol for membership checks"""
        return key in self.__store__

    def __len__(self):
        """Implements protocol for finding length"""
        return len(self.__store__)

    def __eq__(self, other):
        """Implements equality check"""
        if not isinstance(other, type(self)):
            return False
        results = []
        for key in self.__key__.parts:
            if key in other:
                if self[key] == other[key]:
                    results.append(True)
                else:
                    results.append(False)
        return all(results)

    def __hash__(self) -> int:
        keys = []
        for key in self.__key__.parts:
            value = getattr(self, key)
            keys.append(value)
        return hash(tuple(keys))


"""
Expando:

This is a Model to which you can add key/value pairs arbitrarily. 
Expando gives you a *wide* & expandable object through a dict like protocol which can be stored/read 
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

Finally, Expando keys and values are any hashable, and pickleable python object for maximum flexibility. 

LIMITATIONS
============
It is tempting to use Expando as a cache; we *strongly* advise you not to do so, because Expando 
can only support a maximum of 65,535 keys, and must be less than 2GB in size due to internal C* limitations. 

We have  designed and provided the appropriately named cache package for ephemeral storage. 

Here's how you use an Expando:

```python
# Inherit from `Expando` which allows you to add instance/class methods to your Entity

class Author(Expando):
    pass
    
# Or you can use the functionally equivalent one-liner below if you don't need a full fledged class.

Author = Table("Author", Expando)
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
author.save()                                                                        # Save the entire entity

name = author.get("name")                                                            # Fetch local version of a single key
name, category address = author.get("name", "category", "address")                   # Fetch local version of multiple keys 
author.put({"name" : "Sun Tzu", "address" : "1, Santa Clara, California"})           # Add multiple keys with a TTL to Expando 
author.put({"name": "Confucius", "ttl": days(20)})                                   # Add key/value with a TTL

authors = Author.objects.all()                                                      # Retrieve all Author entities from C*
results = (Author
    .objects
    .contains(entry=("name", "Sun Tzu"))                                           # Find all Author by `key, value entry`
.execute()
)

results = (Author
    .objects
    .contains(value="Sun Tzu")  
.execute()
)                                                                                  # Find Authors by `value`
```
"""


class Expando(Model):
    """A dynamically expandable and durable object"""

    def __new__(cls, *arguments, **keywords):
        from cqlalchemy.core.commons import Name, Pickle, Map

        if not hasattr(cls, "data"):
            cls.data = Map(Name, Pickle, index=True)
        else:
            if not isinstance(cls.data, Map):
                raise AttributeError(
                    "The `data` attribute of an Expando must be a Map<T,V>"
                )
        instance = Model.__new__(cls)
        return instance

    def __init__(self, **keywords):
        super().__init__()
        self.data = keywords.pop("data", {})
        for name, value in keywords.items():
            self[name] = value

    def __setitem__(self, key, value):
        """Allows dictionary style item sets to behave properly"""
        if key in RESERVED:
            raise BadValueError(f"Attribute Name: `{key}` is a reserved word")
        if key in self.__properties__:
            setattr(self, key, value)
        else:
            self.data[key] = value

    def __delitem__(self, key):
        """Allows dictionary style item deletions to work properly"""
        if key in self.__properties__:
            delattr(self, key)
        else:
            del self.data[key]

    def __getitem__(self, key):
        """Allows dictionary style item access to behave properly"""
        if key in self.__properties__:
            return getattr(self, key)
        else:
            return self.data[key]

    def __contains__(self, key):
        """Does this model contain this key"""
        if key in self.__store__ or key in self.data:
            return True
        else:
            return False

    def get(self, *columns):
        """Reads multiple properties with one call"""
        results = []
        for name in columns:
            result = self.data.get(name, None)
            results.append(result)
        return results

    def put(self, items: dict):
        """Alternative set that allows multiple properties and specifying ttl"""
        ttl = items.pop("ttl", 0)
        changed = False
        for name, value in items.items():
            if name in self.__properties__:
                self.set(name, value, ttl=ttl)
                changed = True
            else:
                self.data.set(name, value, ttl)
                changed = True
        if changed:
            self.save()

    def has(self, key=None, value=None, entry=None):
        """Checks for this key, value or entry on this Expando"""
        if key:
            return key in self
        elif value:
            for var in self.__store__.values():
                if var == value:
                    return True
            for var in self.data.values():
                if var == value:
                    return True
            return False
        elif entry:
            key, value = entry[0], entry[1]
            if key in self.__store__:
                return value == self.__store__[key]
            if key in self.data:
                return value == self.data[key]
            return False
        else:
            return False

    def __eq__(self, other):
        """Checks if two Expando objects are equal"""
        if not type(other) == type(self):
            return False
        us = getattr(self, "id", None)
        them = getattr(other, "id", None)
        return us == them

    def __hash__(self) -> int:
        """A compatible has implementation that respects __eq__"""
        keys = []
        for key in self.__key__.parts:
            value = getattr(self, key)
            keys.append(value)
        return hash(tuple(keys))


"""
Vector:

This is a durable ordered Vector object for C*, which supports LIFO (Stack) or FIFO (Queue) access styles.

You can store any object that can be pickled into a Vector. Operations on Vector happens in batches to 
improve reliablity since Vector is not idempotent. Vectors are useful when you want to persist a large (automatically) 
indexed contiguous list of similar objects to C*, in order to query and operate upon later.

Vector is also an innately TTL aware Entity.

LIMITATIONS
============
1. Vector can only support a maximum of 65,535 objects and must be less than 2GB in size due to internal C* limitations.
2. Operations on Vector are not idempotent; if you need idempotency consider using a Block, or Expando. 
3. Vector is not synchronized; the underlying representation may be modified by another C* client concurrently (unless you use Locks).
4. Vector fetches its entire data into memory upon query, please keep this in mind to manage memery pressure for your application

This is how to use a Vector:

```python
class Basket(Vector, expire=30, version=True):
    pass

# You an also use the functional style (all supported Entity class parameters are available)

Basket = Table("Basket", Vector, expire=30, version=True)

# Create a Basket and add some fruits, and persist it to C*

fruits = Basket.create()
fruits.extend(["Apple", "Banana", "Watermelon", "Grapes"])

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

fruits.stream()                                  # This tells Vector to save every change/call immediately to C*
fruits.insert(0, "Lemon")
fruits.pop(0)
fruits.remove("Carrot")    

# You can provide a TTL when you append or prepend new objects into a Vector
fruits.append("Cashew", ttl=10)
fruits.prepend("Strawberries", ttl=0)

# You may query all instances of Basket, 
for basket in Basket.objects.all():
    print(basket)

# Or search for Basket which contains a specific Fruit in all the Basket(s)
basket = (Basket
    .objects
    .contains("Pear")\ 
.get())                                        
```
"""


class Vector(Model):
    """A Durable One Dimensional Vector"""

    def __new__(cls, *arguments, **keywords):
        from cqlalchemy.core.commons import Pickle, List

        if not hasattr(cls, "data"):
            cls.data = List(Pickle, index=True)
        else:
            if not isinstance(cls.data, List):
                raise AttributeError(
                    "The `data` attribute of an Expando must be a List<E>"
                )
        instance = Model.__new__(cls)
        return instance

    def __init__(self, **keywords):
        """Create a Vector using the default constructor"""
        super().__init__()
        self.data = keywords.pop("data", [])
        for name, value in keywords.items():
            self[name] = value
        self._stream_ = False

    def stream(self, on=True):
        """Save this Vector upon every successful change"""
        self._stream_ = on

    def prepend(self, value, ttl=0):
        """Prepends @value to this Vector"""
        self.data.prepend(value, ttl)
        if self._stream_:
            self.save()

    def append(self, value, ttl=0):
        """Appends @value to this Vector"""
        self.data.append(value, ttl)
        if self._stream_:
            self.save()

    def extend(self, values: Iterable, ttl=0):
        """Extends this Vector with values from @values"""
        self.data.extend(values, ttl)
        if self._stream_:
            self.save()

    def insert(self, index, value, ttl=0):
        """Inserts @value at @index in this Vectors"""
        self.data.insert(index, value, ttl)
        if self._stream_:
            self.save()

    def __setitem__(self, index, value):
        """Access descriptors or indices for this Vector"""
        if index in self.__properties__:
            setattr(self, index, value)
        else:
            self.data.insert(index, value)
        if self._stream_:
            self.save()

    def __getitem__(self, index):
        """Access descriptors or indices for this Vector"""
        if index in self.__properties__:
            return getattr(self, index)
        else:
            return self.data[index]

    def __str__(self):
        return str(f"{self.__class__.__name__}(id={self.id}, {self.data})")

    def __contains__(self, item):
        return item in self.data

    def __delitem__(self, index):
        """Deletes descriptors or indices for this Vector"""
        if index in self.__properties__:
            delattr(self, index)
        else:
            del self.data[index]
        if self._stream_:
            self.save()

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        for atom in self.data:
            yield atom


"""
Block:

This is a durable unorderd, sorted Set for C*.

You can store any object that can be pickled into a Block. Operations on Set happens in batches to 
improve performance. Blocks are useful when you want to persist a large (automatically) indexed contiguous set
of similar objects to C*, in order to query and operate upon later.

Unlike Vector, operations on Block are idempotent. Set is also an innately TTL aware Entity.

LIMITATIONS
============
1. Block can only support a maximum of 65,535 objects, and must be less than 2GB in size due to internal C* limitations.  
4. Vector fetches its entire data into memory upon query, please keep this in mind to manage memery pressure for your application

This is how to use a Block:

```python
class Basket(Block):
    pass

# You can also use the functional style to create Block objects

Basket = Table("Basket", Block)

# Create a new Basket row, add some fruits, and persist it to C*

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

# You can also update/delete data, immediately in place. Executing your change incurs the cost 
# of a network call to C*, but it also saves you from having to sending large data set over the wire upon batch save. 

fruits.stream()
fruits.add("Lemon")

# You can provide a TTL when you add new objects into Block
fruits.add("Cashew", ttl=10)

# You may query all instances of Basket, 
for basket in Basket.objects.all():
    print(basket)

# Or search for a Basket that contains a specific Fruit in all the Basket(s) in C*
basket = (Basket
    .objects
    .contains("Pear")                                        
.get())
```
"""


class Block(Model):
    """A C* Durable Set"""

    def __new__(cls, *arguments, **keywords):
        from cqlalchemy.core.commons import Pickle, Set

        if not hasattr(cls, "data"):
            cls.data = Set(Pickle, index=True)
        else:
            if not isinstance(cls.data, Set):
                raise AttributeError(
                    "The `data` attribute of an Expando must be a List<E>"
                )
        instance = Model.__new__(cls)
        return instance

    def __init__(self, **keywords):
        """Create a Block"""
        super().__init__()
        self.data = keywords.pop("data", set())
        for name, value in keywords.items():
            self[name] = value
        self._stream_ = False

    def stream(self, on=True):
        """Save this Block upon every successful change"""
        self._stream_ = on

    def add(self, value, ttl=0):
        """Validates and adds a new item to this Set<T>"""
        self.data.add(value, ttl)
        if self._stream_:
            self.save()

    def extend(self, value: Iterable, ttl: int = 0):
        for atom in value:
            self.data.add(atom, ttl)
        if self._stream_:
            self.save()

    def remove(self, value):
        """Validates and removes an item from this Set<T>"""
        self.data.remove(value)
        if self._stream_:
            self.save()

    def __str__(self):
        return str(f"{self.__class__.__name__}(id={self.id}, {self.data})")

    def __contains__(self, item):
        return item in self.data

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        for atom in self.data:
            yield atom


"""
Counter:

Provides C* backed counter objects for use in your applications - without the risk of 
common usage anti-patterns.

Here is a simple Counter:

```python
Analytics = Counter("Analytics", ["errors", "users",])

stats = Analytics.create()
stats.increment("users")
stats.decrement("errors", by=1)
stats.save()

stats = Analytics.read(stats["id"])
count = stats["users"]
stats.save()
```

How to fetch an already existing Analytics object from C*

```python
stats = Analytics.read(stats["id"])
print("Accounts: %s" % stats.get("users"))
```
"""


class CounterModel(Entity):
    """Model for Counter objects"""

    def __new__(cls, *arguments, **keywords):
        """Customizes all Model instances to include special attributes"""
        from cqlalchemy.connection.table import CounterTable as Table
        from cqlalchemy.core.differ import CounterTracker

        cls.__properties__ = fields(cls, Property)
        cls.__fields__ = fields(cls, CqlProperty)

        keys = set()
        for name, property in cls.__fields__.items():
            property.configure(name, cls)
            if name.startswith("_"):
                raise BadValueError(
                    "An Entity attributes cannot begin with an underscore"
                )
            if not name.islower():
                raise BadValueError("Entity attribute names must be lower case")
            if name in RESERVED:
                raise BadValueError(f"Entity attribute `{name}` is a reserved name")
            if hasattr(property, "key") and property.key:
                keys.add(name)
            if not (property.key or property.ctype == "counter"):
                raise BadValueError(
                    f"CounterModel may only have `key` attributes and `counter` types"
                )
        # If there is no defined key, create a default primary key for the Entity.
        if not keys:
            cls.id = UUID(primary=True)

        cls.__table__ = Table(cls)
        cls.__key__ = Key.create(cls)
        instance = super().__new__(cls)
        instance.__store__ = {}
        instance.__pointer__ = None
        instance.__saved__ = False
        instance.__tracker__ = CounterTracker(
            instance, exclude=["__tracker__", "expire", "history"]
        )
        return instance

    @classmethod
    def create(self, **arguments):
        """Creates a new Model, saves it and then returns it"""
        unique = arguments.pop("unique", False)
        instance = self()
        for name in arguments:
            setattr(instance, name, arguments[name])
        self.__table__.save(instance, unique=unique)
        instance.__saved__ = True
        return instance

    @property
    def key(self):
        """Returns the Pointer for this Entity"""
        return self.__pointer__

    def increment(self, counter: str, by: int = 1):
        """Increment a counter on this Model by @"""
        if counter in self.__fields__:
            value = self[counter]
            self[counter] = value + by
        else:
            raise ValueError(f"We did not find any `counter` named {counter}")

    def decrement(self, counter: str, by: int = 1):
        if counter in self.__fields__:
            value = self[counter]
            self[counter] = value - by
        else:
            raise ValueError(f"No `counter` named {counter} in your Model")

    def __setitem__(self, key, value):
        """Access descriptors or indices for this Vector"""
        if key in self.__properties__:
            setattr(self, key, value)
        else:
            raise KeyError(f"{key} was not found in this `CounterModel`")

    def __getitem__(self, key):
        """Access descriptors or indices for this CounterModel"""
        if key in self.__properties__:
            return getattr(self, key)
        else:
            raise KeyError(f"{key} was not found in this `CounterModel`")

    def get(self, *counters):
        """Returns the value for the `counters` specified"""
        results = []
        for name in counters:
            if name in self.__fields__:
                value = getattr(self, name)
                results.append(value)
        return results

    def saved(self):
        """Returns True if we have been saved before or our keys have changed"""
        if not self.__saved__:
            return False
        self.validate()
        new = Pointer.create(
            self
        )  # Create a new disposable Pointer to check for change in the Entity keys.
        if new == self.__pointer__ and self.__saved__:  # The key has not changed,
            return True
        else:
            return False

    @classmethod
    def read(self, key: Union[Pointer, dict, object]):
        """Fetches the Entity identified by @key from C*"""
        pointer = None
        if not isinstance(key, (Pointer, dict)):
            if len(self.__key__.parts) == 1:
                name = list(self.__key__.parts)[0]
                arguments = dict()
                arguments[name] = key
                pointer = Pointer(self.table(), **arguments)
            else:
                raise BadValueError(
                    "You have more than one `key` attribute defined in your Entity"
                )
        elif isinstance(key, Pointer):
            pointer = key
        else:
            pointer = Pointer(self.table(), **key)
        found = self.__table__.read(pointer)
        if found:
            found.__saved__ = True
        return found

    @classmethod
    def refresh(self, instance):
        """Reloads @instance with the latest data from C*"""
        if not instance.saved():
            raise ValueError("You can only refresh a saved Entity")
        instance.validate()
        new = self.read(instance.key)
        return new

    def validate(self):
        """Checks if a Counter Model can be persisted to C*"""
        for name, prop in self.__fields__.items():
            if hasattr(prop, "required") and prop.required:
                value = getattr(self, name, None)
                if prop.empty(value):
                    raise BadValueError("Property: %s is required" % name)
            elif hasattr(prop, "key") and prop.key:
                value = getattr(self, name)
                if prop.empty(value):
                    raise BadValueError(
                        "Property: %s is a key so it is required" % name
                    )
        if not self.__pointer__:
            self.__pointer__ = Pointer.create(self)

    def save(self, unique=False):
        """Stores this Counter Model to C*"""
        self.validate()
        self.__table__.save(self, unique)
        self.__saved__ = True


def Counter(name, counters: List[str,], keyspace=None):
    """Creates a CounterModel with the `counter` columns you specify in @counters"""
    from cqlalchemy.core.commons import Counter64

    descriptors = dict()
    for var in counters:
        descriptors[var] = Counter64()
    kind = type(
        name, (CounterModel,), descriptors, keyspace=keyspace, version=False, expire=0
    )
    return kind
