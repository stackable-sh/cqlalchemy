from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.differ import commit, changes, Action
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import Integer, Float, String


class TestDiffer(TestCase):
    """Basic tests for the current differ implementation"""

    def setUp(self):
        """Creates a sample class with a Default Property installed on it"""
        cqlalchemy.configure(
            keyspace="Test",
            servers=[
                "localhost",
            ],
            debug=True,
            verbose=True,
        )

    def tearDown(self):
        clear()
        return super().tearDown()

    def testSanity(self):
        """Sanity tests for differ"""

        class Example(Model):
            name = String(key=True)
            count = Integer()
            price = Float()

        example = Example(price=3.142, name="Hello", count=500)
        ops = {operation.name for operation in changes(example)}

        self.assertTrue("name" in ops)
        self.assertTrue("price" in ops)
        self.assertTrue("count" in ops)
        commit(example)

        ops = {operation.name for operation in changes(example)}
        self.assertFalse(ops)
        self.assertFalse("name" in ops)
        self.assertFalse("price" in ops)
        self.assertFalse("count" in ops)

        delattr(example, "price")
        example.name = "World"
        ops = {operation.name for operation in changes(example)}
        self.assertTrue(ops)
        self.assertTrue(len(ops) == 2)
