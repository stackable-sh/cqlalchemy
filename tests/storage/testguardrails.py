import uuid
from unittest import TestCase, skip, expectedFailure

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, UUID
from cqlalchemy.core.commons import String, Map, List, Set, Tuple, Integer
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    """Base class for C* related tests"""

    @classmethod
    def keyspace(cls):
        return f"{cls.__name__}Auto"
    
    @classmethod
    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            self.shutdown = False
            cqlalchemy.configure(
                keyspace=self.keyspace(),
                servers=[
                    "localhost",
                ],
                debug=True,
                verbose=True,
            )
        except Exception as e:
            print(e)

    @classmethod
    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            if not self.shutdown:
                self.shutdown = True
                Schema.destroy()
        except Exception as e:
            raise e
        finally:
            clear()     


class TestStaticColumnGuardRails(Base):
    """Tests whether we can catch errors at the model level before we get to C*"""

    def testUpdateMultipleColumns(self):
        """Tests that we can update with static columns an entity on C*"""
        try:

            class Book(Model):
                id = UUID(primary=True)
                name = String(index=True, required=True)
                author = String(key=True)
                owner = String(static=True)
                publisher = String(index=True, required=True)

            book = Book.create(
                name="A Tale of Two Cities", 
                publisher="Amazon Kindle",
                author="Mark Twain",
                owner="Jeff Bezos"
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book["author"], "Mark Twain")
            self.assertEqual(book["owner"], "Jeff Bezos")
        except Exception as e:
            raise e
        finally:
            self.tearDown()
    
    @expectedFailure
    def testUpdateSingleColumn(self):
        """Tests that we can update with static columns an entity on C*"""
        try:

            class Book(Model):
                id = UUID(primary=True)
                name = String(index=True, required=True)
                author = String(key=True)
                owner = String(static=True)
                publisher = String(index=True, required=True)

            book = Book.create(
                name="A Tale of Two Cities", 
                publisher="Amazon Kindle",
                author="Mark Twain",
                owner="Jeff Bezos"
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book["author"], "Mark Twain")
            self.assertEqual(book["owner"], "Jeff Bezos")

            book.owner = "Beff Jezos"
            book.save()
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpsert(self):
        """Tests that we can update an existing C* object in place"""
        try:
            class Book(Model):
                id = UUID(primary=True)
                name = String(index=True)
                author = String(key=True)
                owner = String(static=True)
                publisher = String(index=True)

            book = Book.create(
                name="A Tale of Two Cities", 
                publisher="Amazon Kindle",
                author="Mark Twain",
                owner="Jeff Bezos"
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book["author"], "Mark Twain")
            self.assertEqual(book["owner"], "Jeff Bezos")


            var = book.id
            found = Book.upsert(
                id=var, 
                author="Mark Twain", 
                owner="Beff Jezos"
            )

            self.assertEqual(book, found)
            self.assertEqual(found["owner"], "Beff Jezos")
            
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    @skip
    def testDelete(self):
        """Tests that we can delete an existing C* object in place"""
        from cqlalchemy.connection.cql import Level

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(
                name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            pointer = book.key
            Book.delete(pointer)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    