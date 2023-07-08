from unittest import TestCase
from cqlalchemy.core.models import BadValueError, UUID


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
