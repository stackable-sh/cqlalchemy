from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String
from cqlalchemy.connection.table import Schema
from cqlalchemy.connection.functions import when
from cqlalchemy.connection.cql import Level


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
                servers=["localhost",], 
                debug=True, 
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


class TestHistory(Base):
    """Test the persistence functionality of Model"""

    @skip
    def testSave(self):
        """Tests that we can create an entity on C*"""
        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEquals(instance, book)
    
            instance.publisher = "Barnes & Noble"
            instance.set(
                name="name", 
                value="Adventures of Huckleberry Finn",
                predicate=when(name="A Tale of Two Cities"),
            )
            instance.save()

            instance = Book.refresh(instance)
            changes = list(instance.history.all())

            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")
            self.assertTrue(len(changes) == 2)

            for change in changes:
                change.summary()
        except Exception as e:
            raise e
    
    def testUndo(self):
        """Tests that we can create an entity on C*"""
        import time
        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEquals(instance, book)
    
            instance.publisher = "Barnes & Noble"
            instance.set(
                name="name", 
                value="Adventures of Huckleberry Finn",
                predicate=when(name="A Tale of Two Cities"),
            )
            instance.save()

            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")

            change = instance.history.oldest()
            change.revert()

            time.sleep(10)
            with Level.All:
                found = Book.read(instance.key)
                print(found.name)
                print(found.publisher)
                self.assertTrue(found.name == "A Tale of Two Cities")
                self.assertTrue(found.publisher == "Amazon Kindle")
        except Exception as e:
            raise e
    


