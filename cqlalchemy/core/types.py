# Copyright 2026 Iroiso Ikpokonte
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from typing import Iterable
from collections.abc import MutableMapping, MutableSet, MutableSequence

import bcrypt
import babel.numbers

from cassandra.util import SortedSet

from cqlalchemy.core.builtins import size
from cqlalchemy.exceptions import BaseException
from cqlalchemy.core.differ import TrackableMixin, CollectionTracker, Action
from cqlalchemy.core.models import Converter, Reference, Entity, Collection

__all__ = [
    "phone",
    "password",
    "currency",
    "country",
    "duration",
    "day",
    "Map",
    "Set",
    "List",
]

MAX_BYTES_SIZE = 2**32 - 1  # 1 MB recommended
MAX_LENGTH_COLLECTION = 2**16 - 1


class ContainerException(BaseException):
    """Container Related Exceptions"""

    pass


class Container(object):
    """Base for all Container Type objects"""

    pass


class phone(object):
    """An immutable Phone number in international format"""

    pattern = re.compile(r"^\+(?:[0-9] ?){6,14}[0-9]$")

    def __init__(self, number):
        """Simply pass in the number as one block."""
        if isinstance(number, (str,)):
            number = number.strip()
            if not self.pattern.match(number):
                raise ValueError("Provide an E.164 compliant phone number")
            self._number_ = number
        elif isinstance(number, phone):
            self._number_ = number.number
        else:
            raise ValueError("Please provide a `str` phone number")

    @property
    def number(self):
        """A readonly property that returns the number part of this phone number"""
        return self._number_

    def __eq__(self, other):
        """Equality tests"""
        if isinstance(other, phone):
            return self.number == other.number
        elif isinstance(other, str):
            return self.number == other
        else:
            raise ValueError("%s must be a valid phone number" % other)

    def __str__(self):
        return self.number


class password(object):
    def __init__(self, hash=None, salt=None, text=None):
        if hash and isinstance(hash, (str, bytes)):
            self._secret_ = hash.encode() if isinstance(hash, str) else hash
        else:
            if salt and text:
                if not isinstance(salt, (bytes, str)):
                    raise ValueError(
                        "Provide a `salt` that is either a `str` or `bytes`"
                    )
                if not isinstance(text, (bytes, str)):
                    raise ValueError(
                        "Provide a `text` that is either a `str` or `bytes`"
                    )
                self.salt = salt.encode() if isinstance(salt, str) else salt
                text = text.encode() if isinstance(text, str) else text
                self._secret_ = bcrypt.hashpw(text, self.salt)
            else:
                raise ValueError("Provide a `salt` and `text` parameters")

    def match(self, other):
        if isinstance(other, password):
            return other.hash == self.hash
        elif isinstance(other, (str, bytes)):
            other = other.encode() if isinstance(other, str) else other
            return bcrypt.checkpw(other, self._secret_)
        else:
            raise ValueError("Please provide a `bytes`, `str` or `password` object")

    @property
    def hash(self):
        return self._secret_

    def __str__(self):
        return self.hash.decode()

    def __eq__(self, other):
        return self.match(other)


class currency(object):
    def __init__(self, code):
        if isinstance(code, (str,)):
            if babel.numbers.get_currency_name(code):
                self.code = code
            else:
                raise ValueError("Provide a valid currency code")
        elif isinstance(code, currency):
            self.code = code.code
        else:
            raise ValueError("Please provide a `str`")

    @property
    def name(self):
        return babel.numbers.get_currency_name(self.code)

    @property
    def symbol(self):
        return babel.numbers.get_currency_symbol(self.code)

    def __eq__(self, other):
        if isinstance(other, currency):
            return self.code == other.code
        elif isinstance(other, str):
            return self.code == other
        else:
            raise ValueError("%s must be a valid currency" % other)

    def __str__(self):
        return self.code


class country(object):
    """A country in a locale specific format"""

    def __init__(self, code, locale="en"):
        if isinstance(code, (str,)):
            code = code.upper()
            if babel.Locale(locale).territories.get(code):
                self.code = code
                self.locale = locale
            else:
                raise ValueError("Provide a valid country code")
        elif isinstance(code, country):
            self.code = code.code
            self.locale = code.locale
        else:
            raise ValueError("Please provide a `str`")

    @property
    def name(self):
        return babel.Locale(self.locale).territories.get(self.code)

    @property
    def symbol(self):
        return self.code

    def __eq__(self, other):
        if isinstance(other, country):
            return self.code == other.code
        elif isinstance(other, str):
            return self.code == other
        else:
            raise ValueError("%s must be a valid country or code" % other)

    def __str__(self):
        return self.code


class day(object):
    """A day of the week in a locale specific format"""

    weekdays: int = 7

    def __init__(self, index: int | str, locale="en"):
        if isinstance(index, (int,)):
            if not (0 <= index < self.weekdays):
                raise ValueError("Provide a valid day index")
            else:
                self.index = index
                self.locale = locale
        elif isinstance(index, (str,)):
            value: int = None
            name: str = index
            formats = ["abbreviated", "narrow", "wide", "short"]
            for format in formats:
                names = babel.dates.get_day_names(
                    width=format, context="format", locale=locale
                )
                name_to_index = {
                    name.lower(): int(index) for index, name in names.items()
                }
                if name.lower() in name_to_index:
                    value = name_to_index.get(name.lower(), None)
                    break
            if value is None:
                raise ValueError("Provide a valid day name")
            else:
                self.index = value
                self.locale = locale
        else:
            raise ValueError("Please provide a valid day name or day index")

    @property
    def name(self):
        names = babel.dates.get_day_names(
            width="wide", context="format", locale=self.locale
        )
        return names[self.index]

    @property
    def position(self):
        locale = babel.Locale(self.locale)
        return (self.index - locale.first_week_day) % self.weekdays

    def __eq__(self, other):
        if isinstance(other, day):
            return self.index == other.index
        elif isinstance(other, int):
            return self.index == other
        elif isinstance(other, str):
            return self.index == day(other, locale=self.locale).index
        else:
            raise ValueError("%s must be a valid day name or day index" % other)

    def __hash__(self):
        return hash(self.index)

    def __lt__(self, other):
        return self.position < other.position

    def __repr__(self):
        return f"{self.__class__.__name__}({self.index!r})"

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.index


class duration(object):
    """Represents a duration object that can be in C*"""

    months = 0
    days = 0
    nanoseconds = 0

    def __init__(self, months=0, days=0, nanoseconds=0):
        self.months = months
        self.days = days
        self.nanoseconds = nanoseconds

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) 
            and self.months == other.months 
            and self.days == other.days 
            and self.nanoseconds == other.nanoseconds
        )

    def __repr__(self):
        return "Duration({0}, {1}, {2})".format(self.months, self.days, self.nanoseconds)

    def __str__(self):
        negative = self.months < 0 or self.days < 0 or self.nanoseconds < 0
        return '%s%dmo%dd%dns' % (
            '-' if negative else '',
            abs(self.months),
            abs(self.days),
            abs(self.nanoseconds)
        )
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Map<K, V>

# A mutable hash table that does type, size & length validation before storing items,
# and tracks changes to itself for persistence to C*, otherwise behaves like an ordinary python dict.

# ```python
# table = Map(String, Integer)
# table['count'] = 1

# # Create a Map container without validation

# var = Map()
# table['count'] = "0"

# ```
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class Map(Container, MutableMapping, TrackableMixin):
    """A map that does validation of keys and values"""

    def __init__(self, K=Converter, V=Converter):
        """Initialization routine for Map<K, V>"""
        if not isinstance(K, type):
            raise ValueError("K must be a class")
        if isinstance(K, Collection):
            raise ValueError("You cannot put a Collection in a Map")
        if isinstance(K, Container):
            raise ValueError("You cannot put a Container in a Container")
        if not issubclass(K, (Converter, Entity)):
            raise ValueError("T must be a Converter")

        if not isinstance(V, type):
            raise ValueError("V must be a class")
        if isinstance(V, Collection):
            raise ValueError("You cannot put a Collection in a Map")
        if isinstance(V, Container):
            raise ValueError("You cannot put a Container in a Container :)")
        if not issubclass(V, (Converter, Entity)):
            raise ValueError("V must be a Converter")

        self.type = (K, V)
        self.K = Reference(K) if issubclass(K, Entity) else K()
        self.V = Reference(V) if issubclass(V, Entity) else V()

        self.__store__ = {}
        self.__tracker__ = CollectionTracker(self)

    def __setitem__(self, key, value):
        """Validate and possibly transform key, value before storage"""
        __size__(key, value)
        key, value = self.K(key), self.V(value)
        self.__store__[key] = value
        __length__(self.__store__)
        # Track the change explicitly if the __setitem__ didn't fail.
        operation = self.__tracker__.op(
            code=Action.MADD, parent=self, key=key, value=value
        )
        self.__tracker__.track(operation)

    def set(self, key, value, ttl=0):
        """Sets a value with a TTL to the Map"""
        __size__(key, value)
        key, value = self.K(key), self.V(value)
        self.__store__[key] = value
        __length__(self.__store__)
        # Track the change explicitly if the __setitem__ didn't fail.
        operation = self.__tracker__.op(
            code=Action.MADD, parent=self, key=key, value=value
        )
        operation.ttl = ttl
        self.__tracker__.track(operation)

    def __delitem__(self, key):
        """Validate and possibly transform key before deletion"""
        key = self.K(key)
        del self.__store__[key]
        # Track the change explicitly if the __delitem__ didn't fail.
        operation = self.__tracker__.op(code=Action.MDELETE, parent=self, key=key)
        self.__tracker__.track(operation)

    def __getitem__(self, key):
        """Validate and possibly transform key before retreival"""
        key = self.K(key)
        value = self.__store__[key]
        return value

    def __iter__(self):
        """Returns a iterable over the data set"""
        # If we have References with Models in them, read the Models and return them.
        for k in self.__store__:
            yield k

    def __str__(self):
        """String representation of an object"""
        return str(self.__store__)

    def __eq__(self, other):
        if isinstance(other, Map):
            return self.__store__ == other.__store__
        elif isinstance(other, dict):
            return self.__store__ == other
        else:
            return False

    def __len__(self):
        """Returns the number of the keys in this map"""
        return len(self.__store__)

    def __hash__(self):
        return hash(id(self.__store__))


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# List<T>:

# A mutable sequence that performs validation before storage.

# By default it behaves like an ordinary list. If the data type (the `cls` attribute) of a List is
# a saved Model, the List stores the Model as `Key` object instead of pickling the model.


# ```python
# from cql.core.commons import String

# friends = List(String)
# friends.append("Hello")

# # This does not do any data validation at all.

# friends = List()
# friends[0] = "hello"
# ```
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class List(Container, MutableSequence, TrackableMixin):
    """A List that validates content before addition or removal"""

    def __init__(self, T=Converter):
        """Initializes a List<T> Container"""
        if not isinstance(T, type):
            raise ValueError("T must be a class")
        if isinstance(T, Collection):
            raise ValueError("You cannot put a Collection in a List<T>")
        if isinstance(T, Container):
            raise ValueError("You cannot put a Container in a List<T>")
        if not issubclass(T, (Converter, Entity)):
            raise ValueError("T must be a Converter")
        self.type = T
        self.validate = Reference(T) if issubclass(T, Entity) else T()
        self.__store__ = []
        self.__tracker__ = CollectionTracker(self)

    def prepend(self, value, ttl=0):
        """Prepends an item to this List<T>"""
        __size__(value)
        value = self.validate(value)
        self.__store__.insert(0, value)
        __length__(self.__store__)
        operation = self.__tracker__.op(code=Action.LPREPEND, parent=self, value=value)
        operation.conditions(ttl=ttl)
        self.__tracker__.track(operation)

    def append(self, value, ttl=0):
        __size__(value)
        value = self.validate(value)
        self.__store__.append(value)
        __length__(self.__store__)
        operation = self.__tracker__.op(code=Action.LAPPEND, parent=self, value=value)
        operation.conditions(ttl=ttl)
        self.__tracker__.track(operation)

    def extend(self, values: Iterable, ttl=0):
        """Extends this list with another List<T>"""
        add = []
        for atom in values:
            __size__(atom)
            value = self.validate(atom)
            add.append(value)
        self.__store__.extend(add)
        __length__(self.__store__)
        operation = self.__tracker__.op(code=Action.LAPPEND, parent=self, value=add)
        operation.conditions(ttl=ttl)
        self.__tracker__.track(operation)

    def insert(self, index, value, ttl=0):
        """Validate and possibly transform value before insertion"""
        __size__(value)
        value = self.validate(value)
        self.__store__.insert(index, value)
        __length__(self.__store__)
        operation = self.__tracker__.op(
            code=Action.LINSERT, parent=self, index=index, value=value
        )
        operation.conditions(ttl=ttl)
        self.__tracker__.track(operation)

    def __setitem__(self, index, value):
        """Validate and possibly transform value before adding it to @self"""
        __size__(value)
        value = self.validate(value)
        self.__store__[index] = value
        __length__(self.__store__)
        operation = self.__tracker__.op(
            code=Action.LINSERT, parent=self, index=index, value=value
        )
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
        operation = self.__tracker__.op(code=Action.LDELETE, parent=self, index=index)
        self.__tracker__.track(operation)

    def __len__(self):
        return len(self.__store__)

    def __iter__(self):
        for atom in self.__store__:
            yield atom

    def __hash__(self):
        return hash(id(self.__store__))

    def __eq__(self, other):
        if isinstance(other, List):
            return self.__store__ == other.__store__
        elif isinstance(other, list):
            return self.__store__ == other
        else:
            return False


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Set<T>

# A mutable set that does type validation before adding items to the set.
# By default it behaves like an ordinary set.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class Set(Container, MutableSet, TrackableMixin):
    """A Set that validates content before addition"""

    def __init__(self, T=Converter):
        """Initializes a Set<T> Container"""
        if not isinstance(T, type):
            raise ValueError("T must be a class")
        if isinstance(T, Collection):
            raise ValueError("You cannot put a Collection in a Set")
        if isinstance(T, Container):
            raise ValueError("You cannot put a Container in a Set")
        if not issubclass(T, (Converter, Entity)):
            raise ValueError("T must be a Converter")
        self.type = T
        self.validate = Reference(T) if issubclass(T, Entity) else T()
        self.__store__ = SortedSet()
        self.__tracker__ = CollectionTracker(self)

    def add(self, value, ttl=0):
        """Validates and adds a new item to this Set<T>"""
        __size__(value)
        value = self.validate(value)
        self.__store__.add(value)
        __length__(self.__store__)
        operation = self.__tracker__.op(code=Action.SADD, parent=self, value=value)
        operation.conditions(ttl=ttl)
        self.__tracker__.track(operation)

    def discard(self, value):
        """Validates and removes an item from this Set<T>"""
        value = self.validate(value)
        self.__store__.remove(value)
        operation = self.__tracker__.op(code=Action.SDELETE, parent=self, value=value)
        self.__tracker__.track(operation)

    def __contains__(self, item):
        """Returns True if this item belongs in this Set<T>"""
        value = self.validate(item)
        return value in self.__store__

    def _from_iterable(self, iterable):
        return Set(self.type, iterable)

    def __iter__(self):
        for value in self.__store__:
            yield value

    def __eq__(self, other):
        if isinstance(other, Set):
            return self.__store__ == other.__store__
        elif isinstance(other, set):
            return self.__store__ == other
        else:
            return False

    def __len__(self):
        return len(self.__store__)

    def __hash__(self):
        return hash(id(self.__store__))


def __size__(*values):
    """Implements memory limit checks for C*"""
    if size(values) > MAX_BYTES_SIZE:
        raise ContainerException("Your object: %s is too large" % str(values))


def __length__(value):
    """Implements item limit checks for C*"""
    if len(value) > MAX_LENGTH_COLLECTION:
        raise ContainerException(
            "Your collection object: %s has too many items" % str(value)
        )
