
"""
                        CQLALCHEMY CACHE INTERFACE
                        ====================
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

So basically, our caching API provides you with an infinite, persistent and very fast distributed dictionary with 
a convenient interface built on Apache Cassandra.

OTHER NOTABLE FEATURES
======================
Because the `Cache Interface` this is built on Cassandra it provides:

1. A very fast, durable and always hot cache, you never have to start with a cold cache.   
2. Extremely fast writes, because your write never hits the disk directly.
3. Reasonably fast reads because your data is almost always cached in Memory.
4. Linear scalability, so that adding new nodes to your cluster improves performance.
5. High availability because Cassandra is masterless, distributed, highly resilient to failure
6. Automatic data distribution across the cluster, no need for sharding.
7. Idempotent puts, gets, inserts, upserts, and distributed counters.
8. Tunable consistency and availability according to your performance requirements.
"""

__author__ = "Iroiso Ikpokonte (iroiso@live.com)"

import uuid
import collections
import traceback

from cqlalchemy import Model, Counter, Pickle, String, Integer, Long
from cqlalchemy.options import keyspace
from cqlalchemy.storage.db import BasicCqlQuery

__all__ = [
    "get", "put", "replace", "delete", "incr", "decr", "value", "clear", 
    "time", "FOREVER", "DEFAULT", "CacheMissedError"
]

FOREVER = 0
EMPTY = str(uuid.uuid4())
DEFAULT = 60*60*24*30*3  #ABOUT 90 DAYS BY DEFAULT

class CacheMissedError(Exception):
    """Thrown to signify that a key wasn't found in the cache"""
    pass

"""
counters:

This is the CounterTable for every counter that we will store in the cache. When the cache is 'clear'-ed 
we simply truncate this table and the `EphemeralItem` table.
"""
counters = Counter("EphemeralCounter", String())

"""
EphemeralItem:

Is the cache item stored into cassandra for every key/value pair stored through the API in this module. When the cache 
is 'clear'-ed we simply truncate this table and the `EphemeralCounter` table.
"""
class EphemeralItem(Model):
    '''An Ephemeral Item stored in Cassandra'''
    id = String()
    value = Pickle(required=True)

"""
GET:

Reads a key from the cache returning its value, or else it raises a CacheMissedError. 
If you pass in a keyword value for "default", we return that value instead of raising an error.

If @key is a list or tuple, then this method reads all of them consecutively then returns their values in order.
"""
def get(key, default=EMPTY):
    '''Reads a key or a list of keys from the cache'''
    if not key:
        raise ValueError("You cannot fetch EMPTY|NONE keys from the cache")
    if isinstance(key, str):
        found = EphemeralItem.read(key)
        if found:
            return found.value
        else:
            if default == EMPTY:
                raise CacheMissedError("Didn't find key: %s" % key)
            else:
                return default
    elif isinstance(key, (list, tuple, set)):
        result = []
        for k in key:
            value = get(k, default) # RECURSIVE CALL TO GET
            result.append(value)
        return result
    else:
        raise ValueError("Your key must be a string or a list|tuple|set of strings")

"""
PUT:

Puts a key, value pair idempotently and return 'True' on success and 'False' on failure. 
If key is a Mapping, then we put each of the items in the Mapping into the cache consecutively; 
This operation returns void, and re-raises any error that occurs during the process.

If this key already exists, then this call effectively updates it, you can also use this 
call to increase the TTL for @key.

@unique :  If 'True' then store this key only if it doesn't exist.
@time   :  If not FOREVER, then store this item in cache only for @time seconds.
"""
def put(key, value=None, unique=False, time=DEFAULT):
    '''Stores @key/@value into the cache'''
    if not key:
        raise ValueError("You cannot store EMPTY|NONE keys into the cache.")
    if isinstance(key, str):
        try:
            if not value:
                raise ValueError("You cannot store EMPTY|NONE values into the cache.")
            instance = EphemeralItem(id=key, value=value)
            if time > FOREVER:
                instance.expire = time
            instance.save(unique=unique)
        except Exception as e:
            raise e
    elif isinstance(key, collections.Mapping):
        for name, val in list(key.items()):
            put(name, val, unique, time)
    else:
        raise ValueError("Your key must be a string or a Mapping of key/value pairs")

"""
REPLACE:

This call replaces the value for @key with @replacement only if an item for @key exists and 
its current value is equal to @value. This method is slightly slower than PUT, use it sparingly only 
when necessary since it uses COMPARE & SET under the hood, and the read-before-write anti-pattern.

Returns void like other methods, you have to do a get to see if the replacement succeeded.
"""
def replace(key, value, replacement):
    '''Replace @value with @replacement only if @value exists for @key'''
    if not key or value is None or replacement is None:
        raise ValueError("You cannot store EMPTY|NONE into the cache.")
    try:
        found = EphemeralItem.read(key)
        if not found:
            raise CacheMissedError("Key: %s does not exist in the cache" % key)
        found.value = replacement
        found.save(when={"value" : value})
    except Exception as e:
        raise e

"""
DELETE:

This call deletes a single key|counter or a set of keys|counters from the cache consecutively. 
This method returns void, if there was an error during the delete, it is raised for you to handle

Note:
Remember that you can have a counter and an item with the same key; deleting one doesn't affect 
the other if they both exist in the cache. To delete a counter you must explicitly set @param counter to True
"""
def delete(key, counter=False):
    '''Deletes a key or a set of keys from the cache'''
    if not key:
        raise ValueError("You cannot delete EMPTY|NONE keys from the cache")
    if isinstance(key, str):
        try:
            if not counter:
                EphemeralItem.delete(key)
            else:
                counters.delete(key)
        except Exception as e:
            raise e
    elif isinstance(key, (list, tuple, set)):
        for k in key:
            value = delete(k, counter)
    else:
        raise ValueError("You must pass in a string or a list|tuple|set of strings")

"""
TIME:

Returns the time remaining before @key expires from the cache by
querying for its TTL from Cassandra.
"""
def time(key):
    '''Returns the time remaining before @key expires from the cache'''
    if not key:
        raise ValueError("You cannot query for EMPTY|NONE keys from the cache")
    try:
        q = "SELECT TTL(value) FROM {keyspace}.{kind} WHERE id={id}"
        values = dict()
        values["keyspace"] = keyspace()
        values["kind"] = EphemeralItem.kind()
        values["id"] = EphemeralItem.id.convert(value=key)
        query = BasicCqlQuery(query=q.format(**values))
        row = query.one()
        converters = [Integer(), Long()]
        if row:
            result = row[1][0]
            name, value, stamp, ttl = result
            final = None
            for c in converters:
                try:
                    final = c.deconvert(value)
                    break
                except:
                    continue
            return final
        else:
            raise CacheMissedError("No TTL was found for Key: %s" % key)
    except Exception as e:
        raise e
    
"""
INCR:

This call creates|updates a distributed counter whose key is @key by @delta. This method returns 
the most recent value of the counter or raises and exception if this operation failed.

Counters never expire unless you explicitly delete them; additionally counters are stored in a different 
namespace from key/value items so you could have a counter and an item with the same key and not
have any collisions.
"""
def incr(key, delta=1):
    '''Creates|Increments a distributed counter by @delta'''
    if not key:
        raise ValueError("You cannot store EMPTY|NONE keys in the cache")
    try:
        return counters.upsert(key, delta)
    except Exception as e:
        raise e


"""
VALUE:

Returns the current value of the distributed counter whose key is @key. 
If the counter doesn't exist, we raise a CacheMissedError
"""
def value(key):
    '''Returns the current value of the counter @key'''
    if not key:
        raise ValueError("You cannot read EMPTY|NONE keys from the cache")
    try:
        if isinstance(key, str):
            counter = counters.read(key)
            if counter:
                return counter.value()
            raise CacheMissedError("Counter: %s does not exist in the cache" % key)
        elif isinstance(key, (list, tuple, set)):
            result = []
            for k in key:
                v = value(k)
                result.append(v)
            return result
    except Exception as e:
        raise e
    
"""
DECR:

This call decrements an existing distributed counter whose
key is @key by @delta. This method returns the most recent
value of the counter or raises an Exception if this operation
failed.
"""
def decr(key, delta=1):
    '''Decrements an existing counter by @delta'''
    if not key:
        raise ValueError("You cannot read EMPTY|NONE keys from the cache")
    try:
        return counters.downsert(key, delta)
    except Exception as e:
        raise e

"""
CLEAR:

This call removes all the keys, values and counters from the cache immediately by truncating their tables internally.
This call only affects the current keyspace for cqlalchemy not all keyspaces - however, please be advised to use 
this call carefully; because your cache will be EMPTY after its invocation.

@all   = if True, remove all the Counters and all Items from the cache
@items = if items is True, remove all items stored in the cache, leaving the counters.
"""
def clear(**keywords):
    '''Removes all the keys, values, and counters from the cache'''
    all = keywords.get("all", False)
    items = keywords.get("items", False)
    if all and items:
        raise ValueError("You must set either `all` or `items` not both.")
    if all:
        counters.truncate()
        EphemeralItem.truncate()
    elif items:
        EphemeralItem.truncate()
    else:
        return 