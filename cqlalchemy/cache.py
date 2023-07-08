"""
CACHE
=====
This module provides a fast, high performance and persistent caching API built on Apache Cassandra. 
If you use this module, you can remove memcache/redis and your entire caching layer from your 
infrastracture to lower your costs, reduce maintenance headaches and improve the over all performance of your application.

With the caching API, keys can be any string (choose something unique to minimize key collisions), while values 
can be any pickleable object. We do not enforce any size limits on keys and values, but users must be 
aware that LARGE KEYS/VALUES will have to be transferred over the network and stored in memory by the application 
(until garbage collection).

Also, because the cache module is built on cqlalchemy, it shares the global configuration for cqlalchemy; this implies that each 
application has a caching namespace that is unique to it (stored in the default keyspace) - so your cache keys will not 
collide with the keys of another application and emptying the cache (with `clear()`) only affects your application not 
all applications which use the Cache API (except they use the same keyspace as you). 

Finally, we purposely exempt other complex data structures which Cassandra supports (List, Set, Map) because of the 
limits on item size and the length of the data structure itself.

So basically, our caching API provides you with an (almost) infinite, persistent and very fast distributed dictionary with 
a convenient interface built on Apache Cassandra.

NOTABLE FEATURES
================
Because the `Cache Interface` this is built on Cassandra it provides:

1. A very fast, durable and always hot cache, so you never have to start with a cold cache.   
2. Extremely fast writes, because your write never hits the disk directly.
3. Reasonably fast reads because your data is almost always cached in Memory.
4. Linear scalability, so that adding new nodes to your cluster improves performance.
5. High availability because Cassandra is masterless, distributed, and reasonably resilient to failure
6. Automatic data distribution across the cluster (no need for sharding)
7. Idempotent puts, gets, inserts, and upserts
8. Tunable consistency and availability according to your performance requirements.
"""

from collections.abc import Mapping
from typing import Union, List

from cqlalchemy.time import days
from cqlalchemy.core.models import Model
from cqlalchemy.connection.cql import execute
from cqlalchemy.connection.functions import IN, when
from cqlalchemy.connection.table import Table, Schema
from cqlalchemy.core.commons import Pickle, String

__all__ = [
    "get",
    "put",
    "replace",
    "delete",
    "clear",
    "time",
    "CACHE_MAX_TIME",
    "CacheMissedError",
]


CACHE_MAX_TIME = -1
EMPTY = "pnYnVBlAxL-XmzJbZO-R2OdE90hPdpxgChB7cmSmQtE"
DEFAULT_CACHE_EXPIRY_PERIOD = days(90)


class CacheMissedError(Exception):
    """Thrown to signify that a key wasn't found in the cache"""

    pass


"""
Pair
Is the cache item written into C* for every key/value pair stored.
"""


class Pair(Model, expire=DEFAULT_CACHE_EXPIRY_PERIOD, keyspace="Cache"):
    """An ephemeral item stored into C*"""

    id = String(primary=True)
    value = Pickle(required=True, index=True)


def initialize():
    """Initializes Cache `Pair` in C*"""
    if not Schema.exists(Pair):
        new = Pair()
        Schema.create(new)


"""
get

Reads a key from the cache returning its value, or else it raises a CacheMissedError. 
If you pass in a keyword value for "default", we return that value instead of raising an error.

If @key is a list or tuple, then this method reads all of them consecutively then returns their values in order.
"""


def get(*key, default=EMPTY):
    """Fetch one or many items from Cache"""
    if not key:
        raise ValueError("You cannot fetch EMPTY|NONE keys from the cache")

    initialize()
    if len(key) == 1:
        found = Pair.read(key)
        if found:
            return found.value
        else:
            if default == EMPTY:
                raise CacheMissedError("Key: %s was not found in the datastore." % key)
            else:
                return default
    else:
        query = Pair.objects.where(id=IN(*key)).execute(filter=True)
        fetched = {}
        for pair in query.all():
            fetched[pair.id] = pair.value
        result = []
        for name in key:
            result.append(fetched[name])
        if result:
            return result
        else:
            if default == EMPTY:
                raise CacheMissedError(
                    "Key(s): %s was not found in the datastore." % str(key)
                )
            else:
                return default


"""
put

Sets a key, value pair idempotently into the Cache.

If key is a `mapping`, then we put each of the items in the `mapping`
into the cache consecutively; This operation returns void, and re-raises 
any error that occurs during the process.

If this key already exists, then this call effectively updates it; ergo you can use this 
call to increase the TTL for a `key`.
"""


def put(key, value=None, unique=False, time=DEFAULT_CACHE_EXPIRY_PERIOD):
    """Stores @key/@value into the cache"""
    if not key:
        raise ValueError("You cannot store EMPTY|NONE keys into the Cache.")

    initialize()
    if isinstance(key, str):
        try:
            if not value:
                raise ValueError("You cannot store EMPTY|NONE values into the cache.")
            instance = Pair(id=key, value=value)
            if time > CACHE_MAX_TIME:
                instance.expire = time
            instance.save(unique=unique)
        except Exception as e:
            raise e
    elif isinstance(key, Mapping):
        for name, var in key.items():
            put(name, var, unique, time)
    else:
        raise ValueError("Your key must be a str or Map[str, str]")


"""
replace

This call replaces the `value` for `key` with `replacement` only if an item for `key` 
exists and its current `value` is equal to `value` 
"""


def replace(key, original, replacement):
    """Replace @value with @replacement only if @value exists for @key"""
    if not (key and original and replacement):
        raise ValueError("You cannot store EMPTY|NONE values into the Cache.")

    initialize()
    try:
        Pair.upsert(id=key, value=replacement, predicate=when(value=original))
    except Exception as e:
        raise e


"""
delete

Deletes a `key` or a set of `keys` from the Cache. 
"""


def delete(*key: Union[str, List[str]]):
    """Deletes a `key` or a set of `keys` from the cache"""
    if not key:
        raise ValueError("You cannot delete EMPTY|NONE keys from the Cache")

    initialize()
    if isinstance(key, str):
        try:
            Pair.delete(key)
        except Exception as e:
            raise e
    elif isinstance(key, (list, tuple, set)):
        converter = String()
        keys = [converter.convert(None, value) for value in key]
        query = "DELETE FROM {table} WHERE id IN({keys});"
        query = query.format(table=Pair.table(), keys=",".join(keys))
        execute(query)
    else:
        raise ValueError("You must pass in a `key` of type str or a Iterable[str]")


"""
time

Returns the time remaining before @key expires from the cache by
querying for its TTL from Cassandra.
"""


def time(key):
    """Returns the time remaining before @key expires from the cache"""
    if not key:
        raise ValueError("You cannot query for an EMPTY|NONE `key` from the Cache")

    initialize()
    try:
        query = Pair.objects.ttl("value").where(id=key)
        result = query.get()
        if result:
            return result["value"]
        else:
            raise CacheMissedError("No TTL was found for Key: %s" % key)
    except Exception as e:
        raise e


"""
clear

Empty the cache immediately by truncating all its rows. 
Please use this function with care as it may lead to irrecoverable data loss from the Cache.
"""


def clear():
    """Removes all the keys, values, and counters from the cache"""
    initialize()
    try:
        kind = Table(Pair)
        kind.truncate()
    except Exception as e:
        raise e
