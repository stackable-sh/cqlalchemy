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

from unittest import TestCase
from cqlalchemy.core.models import BadValueError, UUID, TimeUUID


class TestUUID(TestCase):
    """Unittests for the UUID Descriptor"""

    def setUp(self):
        """Create a sample set up object"""

        class Person(object):
            id = UUID()

        self.person = Person()

    def testGeneration(self):
        """Shows that UUID Properties generate UUID's even when they've not been set"""
        value = self.person.id
        self.assertTrue(value is not None)
        self.assertEqual(value, self.person.id)

    def testSanity(self):
        """Shows that UUID Descriptors are READWRITE/DELETE"""
        value = self.person.id
        del self.person.id
        self.assertTrue(self.person.id is not None)
        self.assertNotEqual(value, self.person.id)
        self.person.id = value
        self.assertEqual(value, self.person.id)
        self.assertRaises(BadValueError, lambda: setattr(self.person, "id", "Hello"))


class TestTimeUUID(TestCase):
    """Unittests for the TimeUUID Descriptor"""

    def setUp(self):
        """Create a sample set up object"""

        class Person(object):
            id = TimeUUID()

        self.person = Person()

    def testGeneration(self):
        """Shows that UUID Properties generate UUID's even when they've not been set"""
        value = self.person.id
        self.assertTrue(value is not None)
        self.assertEqual(value, self.person.id)

    def testSanity(self):
        """Shows that UUID Descriptors are READWRITE/DELETE"""
        value = self.person.id
        del self.person.id
        self.assertTrue(self.person.id is not None)
        self.assertNotEqual(value, self.person.id)
        self.person.id = value
        self.assertEqual(value, self.person.id)
        self.assertRaises(BadValueError, lambda: setattr(self.person, "id", "Hello"))
