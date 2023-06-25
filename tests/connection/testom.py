import time
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    '''Base class for C* related tests'''

    def setUp(self):
        '''Configure home globally'''
        try:
            self.shutdown = False
            cqlalchemy.configure(keyspace="Test", servers=["localhost",], debug=True, verbose=True)
        except Exception as e:
            print(e)
            
    def tearDown(self):
        '''Release resources that have been allocated'''
        try:
            if not self.shutdown:
                self.shutdown = True
                Schema.destroy()
                clear()
        except Exception as e:
            raise e


class TestModel(Base):
    """Test the persistence functionality of Model"""

    def testCreate(self):
        """Tests that we can create an entity on C*"""
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()
    
    def testNormalBatchContext(self):
        """Tests whether the Batch Context object works as designed"""
        from cqlalchemy.connection.cql import Batch
        try:
            class Book(Model):
                name = String(index=True, required=True)
                author = String(index=True, required=True)

            results, output = [], []
            with Batch() as b:
                a = Book.create(name="The Great Gasby", author="F. Scott Fitzgerald")
                b = Book.create(name="The Adventures of Huckleberry Finn", author="Mark Twain")
                c = Book.create(name="To Kill a Mockingbird", author="Harper Lee")
                results.extend([a, b, c])
            
            for book in results:
                found = Book.read(book.key)
                output.append(found)
            self.assertTrue(len(output) == 3)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testRead(self):
        """Tests that we can create an entity on C*"""
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
        except Exception as e:
            raise e
        finally:
            self.tearDown()
    
    def testUpdate(self):
        """Tests that we can update an entity on C*"""
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            book.publisher = "Barnes & Noble"
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEquals(instance["publisher"], "Barnes & Noble")
        except Exception as e:
            raise e
        finally:
            self.tearDown()
    
    def testConditionalUpdate(self):
        """Tests that we can update an entity on C*"""
        from cqlalchemy.connection.functions import when
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            book.publisher = "Barnes & Noble"
            book.set("publisher", "Barnes & Noble", when(publisher="Amazon Kindle"))
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEquals(instance["publisher"], "Barnes & Noble")
        except Exception as e:
            raise e
        finally:
            self.tearDown()
    
    def testConditionalDelete(self):
        """Tests that we can update an entity on C*"""
        from cqlalchemy.connection.functions import when
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            book.remove("publisher", when(publisher="Amazon Kindle"))
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertIsNone(instance["publisher"])
        except Exception as e:
            raise e
        finally:
            self.tearDown()
    
    def testCreateIfNotExists(self):
        """Tests that we can create a unique entity on C*"""
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpsert(self):
        """Tests that we can update an existing C* object in place"""
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            var = book.id
            found = Book.upsert(id=var, name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertEqual(book, found)

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
        except Exception as e:
            raise e
        finally:
            self.tearDown()
    
    def testDelete(self):
        """Tests that we can delete an existing C* object in place"""
        from cqlalchemy.connection.cql import Level
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            pointer = book.key
            Book.delete(pointer)
        except Exception as e:
            raise e
        finally:
            self.tearDown()