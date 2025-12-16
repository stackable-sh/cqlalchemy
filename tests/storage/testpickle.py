import pickle
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String
from cqlalchemy.connection.table import Schema
from cqlalchemy.connection.functions import when


class Book(Model, version=True):
    name = String(index=True, required=True)
    publisher = String(index=True, required=True)


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure home globally"""
        try:
            self.shutdown = False
            cqlalchemy.configure(
                keyspace="Test",
                servers=[
                    "localhost",
                ],
                debug=False,
                verbose=True,
            )
            Schema.put(Book)
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


class TestPickle(Base):
    """Test the persistence functionality of Model"""

    def testPickleNormal(self):
        """Tests that we can create an entity on C*"""
        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            output = pickle.dumps(book)
            found = pickle.loads(output)
            self.assertEquals(found.key, book.key)
            self.assertEquals(found, book)
            self.assertTrue(found.name == "A Tale of Two Cities")
            self.assertTrue(found.publisher == "Amazon Kindle")

            found.publisher = "Barnes & Noble"
            found.set(
                "name",
                "Adventures of Huckleberry Finn",
                predicate=when(name="A Tale of Two Cities"),
            )
            output = pickle.dumps(found)
            found = pickle.loads(output)
            found.save()

            instance = Book.read(found.key)
            self.assertEquals(instance, book)
            self.assertTrue(found.name == "Adventures of Huckleberry Finn")
            self.assertTrue(found.publisher == "Barnes & Noble")

        except Exception as e:
            raise e
        finally:
            self.tearDown()
