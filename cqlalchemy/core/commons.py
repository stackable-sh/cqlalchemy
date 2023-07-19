import re
import sys
import gzip
import base64
from enum import Enum, Flag, EnumMeta
from decimal import Decimal
import socket
import ipaddress
import pickle as pickle
import datetime
import urllib.parse

from cassandra.util import OrderedMapSerializedKey, SortedSet

import arrow
from .serialization import quote
from .builtins import assertType
from .types import phone, password, currency
from .types import Map as TypeMap
from .types import Set as TypeSet
from .types import List as TypeList
from .models import Model, Basic, Type, BadValueError
from .models import Collection, CqlProperty, Reference

DEFAULT_BLOB_SIZE_LIMIT = 1024 * 1024 * 5  # 5MB
DEFAULT_STRING_LENGTH_LIMIT = 8192

__all__ = [
    "Integer",
    "Long",
    "String",
    "Choice",
    "Name",
    "Blob",
    "Boolean",
    "URL",
    "Time",
    "DateTime",
    "Phone",
    "Currency",
    "Password",
    "Email",
    "Pickle",
    "Date",
    "Float",
    "Double",
    "Map",
    "Set",
    "List",
    "IP",
    "Decimal",
]

"""
Phone:
A descriptor that stores phone number objects. 

```python
class Story(object):
    channel = String(required=True)
    hotline = Phone(required=True, index=True)
````
"""


class Phone(Basic):
    """An descriptor that contains phone objects"""
    type, ctype = phone, "text"

    def convert(self, instance=None, value=None):
        """Yields the datastore representation of its value"""
        value = self.validate(value)
        return super().convert(instance, value)

    def deconvert(self, value):
        """Converts a value from the datastore to a native python object"""
        if not isinstance(value, str):
            raise BadValueError("Expected a standards compliant phone number in a `str`")
        result = phone(value)
        if not isinstance(result, phone):
            raise BadValueError("Expected a `phone` instance")
        return result

"""
Password: 
Stores a bcrypt encrypted password hash 

```python
class Person(object):
    email = Email(required=True, index=True)
    password = Password(required=True)

person = Person.create(email="john@acme.com", password="hello")
assert person.password.match("hello")
```
"""
class Password(Basic):
    type, ctype = password, "text"

    def __init__(self, **arguments):
        self.salt = arguments.pop("salt", None)
        if not self.salt:
            raise BadValueError("Provide a bcrypt `salt` for hashing your password")
        super().__init__(**arguments)
    
    def convert(self, instance=None, value=None):
        value = self.validate(value)
        return quote(str(value))
    
    def __set__(self, instance, value):
        """Prevents users from overwriting this variable with new data"""
        if isinstance(value, password):
            super().__set__(instance, value)
        elif isinstance(value, (bytes, str)):
            var = value.encode() if isinstance(value, str) else value 
            transformed = password(salt=self.salt, text=var)
            super().__set__(instance, transformed)
        else:
            raise BadValueError("Please provide a `str`, `bytes` or `password` instance")

    def validate(self, value):
        if isinstance(value, password):
            return value 
        elif isinstance(value, str):
            var = value.encode()
            return password(salt=self.salt, text=var)
        else:
            raise BadValueError("Provide a `password` instance")

    def deconvert(self, value):
        if value:
            result = password(hash=value)
            return result
        else:
            return None
    


"""
Currency:
A descriptor that stores currency objects. 

```python
class Product(object):
    currency = Currency(required=True, choices=["USD", "NGN"])
````
"""


class Currency(Basic):
    """An descriptor that contains currency objects"""
    type, ctype = currency, "text"

    def convert(self, instance=None, value=None):
        value = self.validate(value)
        return super().convert(instance, value)

    def deconvert(self, value):
        """Converts a value from the datastore to a native python object"""
        if not isinstance(value, str):
            raise BadValueError("Expected a standards compliant currency code as a `str`")
        result = currency(value)
        if not isinstance(result, currency):
            raise BadValueError("Expected a `phone` instance")
        return result


"""
Float:
A data descriptor for modeling Floats in your 'things'. It coerces like the normal
python float

```python
class Circle(object):
    pi = Float()
```
    
"""


class Float(Basic):
    """A float descriptor"""

    type, ctype = float, "float"


"""
Double:
A descriptor for storing floats with Double precision.

```python
class Circle(object):
    pi = Double()
```
    
"""


class Double(Basic):
    """A float descriptor"""
    type, ctype = float, "double"


"""
Decimal:
A variable precision Decimal that can be stored in C*

```python
class Circle(object):
    pi = Decimal()
``` 
"""


class Decimal(Basic):
    """A variable precision Decimal that can be stored in C*"""
    type, ctype = Decimal, "decimal"


"""
Integer:
A 32bit signed integer stored within C*

```python
class Balls(object)
    number = Integer(choices=range(1,5))
    sold = Integer()
```
    
"""


class Integer(Basic):
    """Data descriptor for an Integer"""
    type, ctype = int, "int"


"""
Long:
A 64bit signed longs stored  within C*

```python
class Balls(object)
    number = Long(choices=range(1,5))
    sold = Long()
```
    
"""


class Long(Basic):
    """Data descriptor for an Integer"""
    type, ctype = int, "bigint"


"""
Counter:
A 64bit signed long that gets stored within C* as a Counter
"""


class Counter64(Basic):
    """Data descriptor for a Counter"""
    type, ctype = int, "counter"


"""
Boolean:
Stores a boolean into C*

```python
class Person(object):
    married = Boolean()
```

person = Person()
person.married = "Married"
assert person.married == True
person.married = True
assert person.married == True

"""


class Boolean(Basic):
    """Stores a boolean value into C*"""
    type, ctype = bool, "boolean"


"""
Choice
Stores Enum and Flag objects in C*

```python
from enum import Enum 

Status = Enum("Status", ["Married", "Single", "Divorce"])

class Person(object):
    status = Choice(Status, index=True)
```

"""


class Choice(Basic):
    type, ctype = Enum, "text"

    def __init__(self, T: EnumMeta, **keywords):
        if not isinstance(T, EnumMeta):
            raise BadValueError("Please provide an Enum Factory object")
        self.enum = T
        super().__init__(**keywords)

    def convert(self, instance=None, value=None):
        return quote(value.name)

    def deconvert(self, value):
        return self.enum[value]

    def validate(self, value):
        value = super().validate(value)
        if isinstance(value, (Enum, Flag)):
            if value in self.enum:
                return value
            else:
                raise BadValueError("Enum: %s is not a part of %s" % (value, self.enum))
        else:
            raise BadValueError("Expected an %s, received: %s" % (Enum, type(value)))


"""
String:
Stores a str object into C*

```python
class Story(object):
    channel = String(required=True)
    reporter = String(length=30)
```
"""


class String(Basic):
    type, ctype = str, "text"

    def __init__(self, **arguments):
        length = arguments.pop("length", 2**8)
        pattern = arguments.pop("pattern", None)
        if length <= 0:
            raise ValueError("Length must be greater than zero")
        self.length = length
        if pattern:
            self.pattern = re.compile(pattern)
        else:
            self.pattern = None
        super(String, self).__init__(**arguments)

    def validate(self, value):
        value = super().validate(value)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf_8", "strict")
        if not isinstance(value, str):
            value = str(value, encoding="utf_8")
        if not len(value) <= self.length:
            raise BadValueError(
                "Expected Length : %s , Got : %s" % (self.length, len(value))
            )
        if self.pattern and not self.pattern.match(value):
            raise BadValueError("Value doesn't match pattern: %s" % self.pattern)
        return value

    def deconvert(self, value):
        """Simply returns the value passed in from the data store"""
        return value
    

"""
Email:
Stores a validated email str into C*

```python
class Story(object):
    channel = String(required=True)
    reporter = Email(required=True, index=True)
```
"""

class Email(String):
    type, ctype = str, "text"
    regex = r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+'

    def __init__(self, **arguments):
        arguments["pattern"] = self.regex
        super().__init__(**arguments)




"""
Text:
Stores a str object into C*

```python
class Story(object):
    channel = String(required=True)
    reporter = String(length=30)
```
"""


class Text(String):
    type, ctype = str, "text"

    def __init__(self, **arguments):
        length = arguments.pop("length", 2**16)
        arguments["length"] = length
        super().__init__(**arguments)


"""
IP:
Validates and Stores IP Addresses (both V4 & V6) in Cassandra
"""


class IP(Basic):
    type, ctype = str, "inet"

    def __init__(self, **keywords):
        """initializes the IP Address"""
        super(IP, self).__init__(**keywords)

    def validate(self, value):
        """Checks that you have set a valid IP address"""
        value = super(IP, self).validate(value)
        try:
            ipaddress.ip_address(value)
            return value
        except Exception as e:
            raise BadValueError("Got invalid IP Address: %s" % str(value))

    def deconvert(self, value):
        """Converts a value from the datastore repr to a native python object"""
        if len(value) == 16:
            fam = socket.AF_INET6
        else:
            fam = socket.AF_INET
        return socket.inet_ntop(fam, value)


"""
Pickle:
Stores pickle-able python objects into C*

```python
class NewsPaper(Model):
    headlines = Pickle(required=True)
```
"""


class Pickle(Basic):
    """Pickles and stores python objects in Cassandra"""

    def __init__(self, **keywords):
        """Initializes the pickle descriptor"""
        self.gzip = keywords.get("gzip", True)
        super(Pickle, self).__init__(**keywords)

    def convert(self, instance=None, value=None):
        """Pickles the underlying object using pickle"""
        value = self.validate(value)
        value = pickle.dumps(value)
        if self.gzip:
            value = gzip.compress(value)
        value = base64.b64encode(value)
        return quote(value.decode())

    def validate(self, value):
        """Pickle can store almost any python object"""
        return value

    def deconvert(self, value):
        """Simply returns the value passed in from the data store"""
        if isinstance(value, (str, bytes)):
            value = base64.b64decode(value)
            if self.gzip:
                value = gzip.decompress(value)
            return pickle.loads(value)
        elif value is None:
            return None
        else:
            raise BadValueError("Pickle can only load `str` objects")


"""
Name:
A String (like) descriptor that allows you to store case-insensitive alpha numeric values with or 
without underscores - with one caveat "values cannot start with underscores". 

This descriptor was designed to allow you to store values that can be used as C* column 
names (and social media usernames) safely.

```python
class Story(object):
    channel = Name(required=True, index=True)
```
"""


class Name(String):
    def __init__(self, **keywords):
        """Construct property"""
        super(Name, self).__init__(**keywords)

    def validate(self, value):
        """Validate length here"""
        value = super(Name, self).validate(value)
        if value:
            value = value.lower()
            if value.startswith("_"):
                raise BadValueError(
                    "This Property doesn't allow values starting with an underscore"
                )
            for c in value:
                valid = bool(c.isalpha() or c == "_")
                if not valid:
                    raise BadValueError(
                        "Value: %s contains an invalid character" % value
                    )
            return value
        else:
            raise BadValueError("You must put a valid alpha numeric string here.")


"""
Blob:
Blob is a data descriptor for storing blobs in C*.
If you set its size parameter to "-1" then this blob can store elements of any size.

```python
class Person(object):
    headshot = Blob(size=1024*50)
```
"""


class Blob(Basic):
    """Store Blobs as Text in Cassandra"""

    type, ctype = bytes, "blob"

    def __init__(self, default="", size=DEFAULT_BLOB_SIZE_LIMIT, **arguments):
        """Creates a Blob descriptor"""
        if "choices" in arguments:
            raise BadValueError("Blob descriptors do not support choices")
        self._size_ = size
        super(Blob, self).__init__(default=default, **arguments)

    def indexed(self):
        """Indexing Blob objects is not supported"""
        return False

    @property
    def size(self):
        """Size limit for Blob objects"""
        return self._size_

    def validate(self, value):
        """Makes sure that whatever you are putting, does not exceed size"""
        size = sys.getsizeof(value)
        if not isinstance(value, bytes):
            try:
                value = bytes(value)
            except Exception:
                raise BadValueError("You can only put a `bytes` into a Blob")
        if size <= self.size or self.size <= -1:
            return value
        else:
            raise BadValueError(
                "Your Blob must be less than: %s , got: %s bytes" % (self.size, size)
            )


"""
URL
A data descriptor that validates strings to make sure they are valid URLs.

```python
class Person(object):
    website = URL(required=True)
```     
"""


class URL(String):
    """Makes sure that a string you are creating is a valid URL"""

    length = 1024  # We cannot store URL's longer than 1024 characters.

    def empty(self, value):
        """What does it mean for a URL to be empty"""
        return value is None or not bool(value.strip())

    def validate(self, value):
        """Uses urlsplit to validate urls"""
        value = super(URL, self).validate(value)
        if value is not None and value.strip():
            parsed = urllib.parse.urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise BadValueError(
                    "Property %s must be a full URL ('%s')" % (self.name, value)
                )
        return value


"""
DateTime:
A descriptor that stores a datetime. It implements 'now' keyword which makes sure
that the the attribute always return the current value from the datetime module

```python
class Person(object):
    birthdate = DateTime()
    modified = DateTime(now=True)
```
"""


class DateTime(Type):
    """Base class of all date time properties"""

    type, ctype = datetime.datetime, "timestamp"

    def __init__(self, **arguments):
        self.auto = arguments.pop("now", False)
        super(DateTime, self).__init__(**arguments)

    def __get__(self, instance, owner):
        """Overrides get to implement auto"""
        if self.auto:
            now = self.now()
            self.__set__(instance, now)
        return super(DateTime, self).__get__(instance, owner)

    def validate(self, value):
        """Add type checking and coercion and automatic construction to basic validation"""
        if not isinstance(value, self.type):
            raise BadValueError("We only accept datetime objects here")
        return value

    def convert(self, instance=None, value=None):
        """Yields the datastore representation of its value"""
        value = self.validate(value)
        value = quote(value.isoformat())
        return value

    def deconvert(self, value):
        """Converts a value from the datastore to a native python object"""
        if value is None:
            return None
        try:
            value = arrow.get(value).datetime
            return value
        except Exception as e:
            raise BadValueError(
                "Expected an ISO 8601 DateTime string from deconversion"
            )

    def serialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, datetime.datetime):
            raise BadValueError("You can only serialize datetime objects")
        return value.isoformat()

    def deserialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, str):
            raise BadValueError(
                "Expected an ISO 8601 DateTime string from deconversion"
            )
        val = arrow.get(value).datetime()
        return val

    def empty(self, value):
        """DateTime's are empty when they are none"""
        return value is None

    def now(self):
        """Helper to return a datetime representing now"""
        return datetime.datetime.now()


"""
Time:
Descriptor for storing timestamps.

```python
class News(object):
    headline = String()
    time = Time()
```
"""


class Time(DateTime):
    """Stores only the time part of a datetime"""
    type, ctype = datetime.time, "time"

    def now(self):
        return datetime.datetime.now().time()

    def validate(self, value):
        """Add type checking and coercion and automatic construction to basic validation"""
        value = super(Time, self).validate(value)
        if not isinstance(value, self.type):
            raise BadValueError("We only accept datetime objects here")
        return value

    def convert(self, instance=None, value=None):
        """Yields the datastore representation of its value"""
        value = self.validate(value)
        value = quote(value.isoformat())
        return value

    def deconvert(self, value):
        """Converts a value from the datastore to a native python object"""
        if value is None:
            return None
        try:
            value = arrow.get(value).time()
            return value
        except Exception as e:
            raise BadValueError(
                "Expected an ISO 8601 DateTime string from deconversion"
            )

    def serialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, self.type):
            raise BadValueError(
                "You cannot serialize a non datetime object with this serializer"
            )
        val = arrow.get(value).time()
        return val.isoformat()

    def deserialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, str):
            raise BadValueError("We expect an ISO 8601 formatted datetime string here")
        val = arrow.get(value).time()
        return val


"""
Date:
Descriptor for storing dates. It stores the date part of a datetime object

```python
class News(object):
    headline = String()
    time = Date()
```

"""


class Date(DateTime):
    """Stores the Date part of a datetime"""

    type, ctype = datetime.date, "date"

    def now(self):
        return datetime.datetime.now().date()

    def validate(self, value):
        """Add type checking and coercion and automatic construction to basic validation"""
        value = super(Date, self).validate(value)
        if not isinstance(value, self.type):
            raise BadValueError("We only accept datetime objects here")
        return value

    def convert(self, instance=None, value=None):
        """Yields the datastore representation of its value"""
        value = self.validate(value)
        value = quote(value.isoformat())
        return value

    def deconvert(self, value):
        """Converts a value from the datastore to a native python object"""
        if value is None:
            return None
        try:
            value = arrow.get(value).date()
            return value
        except Exception as e:
            raise BadValueError(
                "Expected an ISO 8601 DateTime string from deconversion"
            )

    def serialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, self.type):
            raise BadValueError(
                "You cannot serialize a non datetime object with this serializer"
            )
        return value.isoformat()

    def deserialize(self, value):
        """We can serialize basic types by calling str on their value"""
        if not isinstance(value, str):
            raise BadValueError("We expect an ISO 8601 formatted datetime string here")
        val = arrow.get(value).date()
        return val


"""
List:
A descriptor that stores homogeneous lists. List works like the Set descriptor except that 
Lists can accept duplicates. by default it is an empty list.

```python
class Person(object):
    name = String()
    friends = List(String)

person = Person()
person.friends = ["Aisha","Halima","Safia",]
```
"""


class List(Collection):
    """Stores a List of objects,You can specify the type of the objects this list contains"""

    def __init__(self, T, **keywords):
        """Stores a List of objects in C*"""
        if not issubclass(T, (CqlProperty, Model)):
            raise BadValueError("T: {0} must be a CqlProperty or Model".format(T))
        if issubclass(T, Model):
            self.converter = Reference(T)
        else:
            self.converter = T()
        self.type = T
        super(List, self).__init__(**keywords)

    @property
    def ctype(self):
        """A property that generates the ctype of its set dynamically"""
        fragment = "list<{type}>"
        return fragment.format(type=self.converter.ctype)

    def deconvert(self, value):
        """Changes for the CQL driver representation to CqlAlchemy"""
        if isinstance(value, list):
            converted = TypeList(self.type)
            V = self.converter
            for var in value:
                var = V.deconvert(var)
                converted.append(var)
            return converted
        elif value is None:
            return None
        else:
            raise BadValueError("Expected: %s, Recevied: %s" % (list, type(value)))

    def _escape_(self, iterable):
        """Useful for changing a list to it appropriate CQL3 representation"""
        return "[" + ", ".join(iterable) + "]"

    def convert(self, instance=None, value=None):
        """Convert to a suitable CQL representation"""
        if isinstance(value, (list, TypeList)):
            value = self.validate(value)
            property = self.converter
            converted = [property.convert(value=v) for v in value]
            out = self._escape_(converted)
            return out
        else:
            raise BadValueError("Expected: %s, Recevied: %s" % (list, type(value)))

    def validate(self, value):
        """Validates a list and all its contents"""
        if value is None:
            return TypeList(self.type)
        elif isinstance(value, TypeList):
            if value.type == self.type:
                return value
            else:
                raise BadValueError(
                    "Expected List<%s>, Received List<%s>" % (self.type, value.type)
                )
        elif isinstance(value, list):
            out = TypeList(self.type)
            for var in value:
                out.append(var)
            return out
        else:
            raise BadValueError("Expected: %s, Recevied: %s" % (list, type(value)))


"""
Set:
A descriptor that describes homogenuous python sets which can be stored directly in C*

```python
class Person(object):
    spouses = Set(User)
```
"""


class Set(Collection):
    """A data descriptor for storing a Set into C*"""

    def __init__(self, T, **keywords):
        assertType(
            T, (CqlProperty, Model), "T: {0} must be a CqlProperty or Model".format(T)
        )
        if issubclass(T, Model):
            self.converter = Reference(T)
        else:
            self.converter = T()
        self.type = T
        super(Set, self).__init__(**keywords)

    @property
    def ctype(self):
        """A property that generates the ctype of its set dynamically"""
        fragment = "set<{type}>"
        return fragment.format(type=self.converter.ctype)

    def deconvert(self, value):
        """Changes for the CQL driver representation to CqlAlchemy"""
        if isinstance(value, SortedSet):
            converted = TypeSet(self.type)
            V = self.converter
            for var in value:
                var = V.deconvert(var)
                converted.add(var)
            return converted
        elif value is None:
            return None
        else:
            raise BadValueError("Expected: %s, Recevied: %s" % (SortedSet, type(value)))

    def _escape_(self, iterable):
        """Useful for changing a set to it appropriate CQL representation"""
        return "{" + ", ".join(iterable) + "}"

    def convert(self, instance=None, value=None):
        """Convert to a suitable CQL representation"""
        if isinstance(value, (set, TypeSet)):
            value = self.validate(value)
            property = self.converter
            converted = [property.convert(value=v) for v in value]
            out = self._escape_(converted)
            return out
        else:
            raise BadValueError("Expected: %s, Recevied: %s" % (set, type(value)))

    def validate(self, value):
        """Validates a list and all its contents"""
        if value is None:
            return TypeSet(self.type)
        elif isinstance(value, TypeSet):
            if value.type == self.type:
                return value
            else:
                raise BadValueError(
                    "Expected List<%s>, Received List<%s>" % (self.type, value.type)
                )
        elif isinstance(value, (set, list)):
            out = TypeSet(self.type)
            for var in value:
                out.add(var)
            return out
        else:
            raise BadValueError("Expected: %s, Recevied: %s" % (set, type(value)))


"""
Map:
A descriptor for dict-like objects with specific predefined, and validated types.

```python
class Person(object):
    bookmarks = Map(String, URL)
```
"""


class Map(Collection):
    """Map descriptor for dict objects."""

    def __init__(self, K, V, **keywords):
        """Map descriptor for dict objects."""
        assertType(K, (CqlProperty, Model), "K must be a CqlProperty or a Model")
        assertType(V, (CqlProperty, Model), "V must be a CqlProperty")
        self.type = (K, V)
        K = Reference(K) if issubclass(K, Model) else K()
        V = Reference(V) if issubclass(V, Model) else V()
        self.converter = (K, V)
        super(Map, self).__init__(**keywords)

    @property
    def ctype(self):
        """A property that generates the ctype of its set dynamically"""
        fragment = "map<{key},{value}>"
        k, v = self.converter
        return fragment.format(key=k.ctype, value=v.ctype)

    def _escape_(self, iterable):
        """Converts this Map to its appropriate CQL3 representation"""
        return "{"+ ", ".join([key + ":" + value for key, value in list(iterable.items())])+ "}"
        

    def convert(self, instance=None, value=None):
        """Generates the CQL update and insert queries for Map descriptor"""
        value = self.validate(value)
        k, v = self.converter
        converted = {
            k.convert(value=key): v.convert(value=value)
            for key, value in list(value.items())
        }
        output = self._escape_(converted)
        return output

    def deconvert(self, value):
        """Changes the Cassandra generated results to python"""
        if isinstance(value, OrderedMapSerializedKey):
            T, E = self.type
            converted = TypeMap(T, E)
            K, V = self.converter
            for name, value in value.items():
                name, value = K.deconvert(name), V.deconvert(value)
                converted[name] = value
            return converted
        elif value is None:
            return None
        else:
            raise BadValueError(
                "Expected: %s, Recevied: %s" % (OrderedMapSerializedKey, type(value))
            )

    def validate(self, value):
        """Validates that we are setting the right dict type object on the descriptor"""
        if value:
            if isinstance(value, TypeMap):
                if self.type == value.type:
                    return value
                else:
                    raise BadValueError(
                        "%s is a Map<%s, %s>, we require a Map<%s, %s>"
                        % (
                            value,
                            value.type[0],
                            value.type[1],
                            self.type[0],
                            self.type[1],
                        )
                    )
            elif isinstance(value, dict):
                K, V = self.type
                data = TypeMap(K, V)
                data.update(value)
                return data
            else:
                raise BadValueError(
                    "We require a dict or a Map<%s, %s>" % (self.type[0], self.type[1])
                )
        else:
            K, V = self.type
            return TypeMap(K, V)
