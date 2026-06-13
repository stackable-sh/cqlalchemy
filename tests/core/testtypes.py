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

from cqlalchemy.core.types import phone
from cqlalchemy.core.commons import String
from cqlalchemy.core.differ import changed
from cqlalchemy.core.types import List, Map, Set, ContainerException
from unittest import TestCase, skip


class TestPhone(TestCase):
    def testSanity(self):
        with self.assertRaises(ValueError):
            mobile = phone("(0248) 123-7654")
        mobile = phone("+2348094486101")

    def testRepr(self):
        """Makes sure that phones get a valid python repr"""
        mobile = phone("+2348094486101")
        self.assertEqual(mobile, "+2348094486101")

    def testStr(self):
        """Makes sure that phones are properly stringified"""
        mobile = phone("+2342481237654")
        self.assertEqual("+2342481237654", str(mobile))


class TestCollectionDifferLogic(TestCase):
    def testListDiffer(self):
        """Checks that lists can detect changes correctly"""
        s = List(String)
        s.extend(["Hello", "World", "Welcome", "To", "Australia"])
        self.assertTrue(changed(s))
        s.commit()
        self.assertFalse(changed(s))

    def testSetDiffer(self):
        """Checks that sets can detect changes appropriately"""
        s = Set(String)
        for item in ["Hello", "World", "Welcome", "To", "Australia"]:
            s.add(item)
        self.assertTrue(changed(s))
        s.commit()
        self.assertFalse(changed(s))

    def testMapDiffer(self):
        """Checks that maps can detect changes"""
        m = Map(String, String)
        for i, v in enumerate("Hello World Here"):
            m[i] = v
        self.assertTrue(list(m.changes()))
        m.commit()
        self.assertFalse(list(m.changes()))


class TestCollectionLimits(TestCase):
    key, value = "Key" * 65536, "Value" * 65536
    limit = 65536

    def testMapSanity(self):
        """Show that Map respects Cassandra limits"""
        m = Map(String, String)
        with self.assertRaises(Exception):
            m["hello"] = self.value
        with self.assertRaises(Exception):
            m[self.key] = "value"
        with self.assertRaises(Exception):
            m[self.key] = self.value
        with self.assertRaises(Exception):
            for i in range(self.limit):
                m[i] = i

    def testListSanity(self):
        """Show that List respects Cassandra limits"""
        l = List(String)
        with self.assertRaises(Exception):
            l.append(self.value)
        with self.assertRaises(Exception):
            for i in range(self.limit):
                l.append(i)

    def testSetSanity(self):
        """Show that Set respects Cassandra limits"""
        l = Set(String)
        with self.assertRaises(Exception):
            l.add(self.value)
        with self.assertRaises(Exception):
            for i in range(self.limit):
                l.add(i)
