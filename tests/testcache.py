import time
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy import cache
from cqlalchemy.cache import CacheMissedError, CACHE_MAX_TIME
from cqlalchemy.options import clear
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            self.shutdown = False
            cqlalchemy.configure(
                keyspace="CacheTest",
                servers=[
                    "localhost",
                ],
                debug=False,
                verbose=True,
            )
        except Exception as e:
            print(e)

    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            if not self.shutdown:
                self.shutdown = True
                Schema.destroy()
                clear()
        except Exception as e:
            raise e


class TestCacheAPI(Base):
    def testGetWithNoKey(self):
        """Tests the get/put interface of the cache"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)

    def testGetWithMultipleKeys(self):
        """Tests that you can retrieve multiple keys with get"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)
        cache.put("hello", "world")
        cache.put("name", "surname")
        self.assertEqual(cache.get("hello", "name"), ["world", "surname"])

    def testBasicPut(self):
        """Tests that basic put works"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)
        cache.put("hello", "world")
        self.assertEqual(cache.get("hello"), "world")

    def testBasicPutUnique(self):
        """Tests that basic put works"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)
        cache.put("hello", "world")
        self.assertEqual(cache.get("hello"), "world")
        cache.put("hello", "hi", unique=True)
        self.assertEqual(cache.get("hello"), "world")
        cache.put("hello", "hi")
        self.assertEqual(cache.get("hello"), "hi")
        cache.put("batman", "gotham", unique=True)
        self.assertEqual(cache.get("batman"), "gotham")

    def testPutWithTTL(self):
        """Tests that basic put works"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)
        cache.put("hello", "world", time=2)
        self.assertEqual(cache.get("hello"), "world")
        time.sleep(4)
        with self.assertRaises(CacheMissedError):
            self.assertEqual(cache.get("hello"))

    def testTime(self):
        """Tests that basic put works"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)
        cache.put("hello", "world", time=10)
        self.assertEqual(cache.get("hello"), "world")
        time.sleep(1.0)
        remaining = cache.time("hello")
        self.assertTrue(remaining > 0)
        self.assertTrue(remaining < 10)
        with self.assertRaises(CacheMissedError):
            cache.time("name")
        cache.put("tokyo", "japan", time=CACHE_MAX_TIME)
        self.assertTrue(cache.time("tokyo") is not None)
        cache.delete("tokyo")
        with self.assertRaises(CacheMissedError):
            cache.time("tokyo")

    def testMultiplePut(self):
        """Tests that basic put works"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)
        cache.put({"hello": "world", "name": "surname"})
        self.assertEqual(cache.get("hello", "name"), ["world", "surname"])

    def testMultiplePutUnique(self):
        """Tests that basic put works"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)
        cache.put({"hello": "world", "name": "surname"}, unique=True)
        self.assertEqual(cache.get("hello", "name"), ["world", "surname"])
        cache.put({"batman": "gotham", "name": "Dean koontz"}, unique=True)
        self.assertEqual(
            cache.get("hello", "name", "batman"), ["world", "surname", "gotham"]
        )

    def testPutStoresPickleableObjects(self):
        """Tests that basic put works"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        value = cache.get("hello", default=None)
        self.assertTrue(value is None)
        cache.put("hello", ["the", "world", "is", "mine"])
        self.assertEqual(cache.get("hello"), ["the", "world", "is", "mine"])

    def testReplace(self):
        """Tests that basic replace works."""
        cache.put("hello", "world")
        cache.replace("hello", "world", "friend")
        self.assertEqual(cache.get("hello"), "friend")
        cache.replace("hello", "new york", "wrong")
        self.assertEqual(cache.get("hello"), "friend")
        cache.replace("hello", "friend", "london")
        self.assertEqual(cache.get("hello"), "london")

    def testDeleteKey(self):
        """Tests that basic delete works on keys."""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        cache.put("hello", "world")
        self.assertEqual(cache.get("hello"), "world")
        cache.delete("hello")
        with self.assertRaises(CacheMissedError):
            cache.get("hello")

    def testDeleteMultipleKeys(self):
        """Tests that deletes work on multiple keys"""
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        cache.put({"hello": "world", "name": "surname"})
        self.assertEqual(cache.get("hello", "name"), ["world", "surname"])
        cache.delete("hello", "name")
        with self.assertRaises(CacheMissedError):
            print(cache.get("hello"))

    def testClear(self):
        """Tests that you can use clear to empty the cache"""
        cache.put("hello", "world")
        cache.put("name", "iroiso")
        cache.clear()
        with self.assertRaises(CacheMissedError):
            cache.get("hello")
        with self.assertRaises(CacheMissedError):
            cache.get("name")
