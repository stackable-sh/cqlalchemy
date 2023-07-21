from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String
from cqlalchemy.connection.table import Schema
from cqlalchemy.connection.functions import when

# 1. TODO: Test History.rewind on multiple related objects
# 2. TODO: Test objects with collection or references to other Models

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

    def testSave(self):
        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEquals(instance, book)
    
            instance.publisher = "Barnes & Noble"
            instance.name = "Adventures of Huckleberry Finn"
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
            
            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == "Amazon Kindle")

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")
        except Exception as e:
            raise e
    

    def testRestore(self):
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
            change = instance.history.last()

            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")
            
            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == "Amazon Kindle")
            change = instance.history.last()
            journal = change["journal"]
            print(journal)

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")

            instance.history.restore(to=journal)
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == "Amazon Kindle")
        except Exception as e:
            raise e
    
    def testRevert(self):
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

            change = instance.history.first()
            change.revert()

            found = Book.refresh(instance)
            self.assertTrue(found.name == "A Tale of Two Cities")
            self.assertTrue(found.publisher == "Amazon Kindle")
        except Exception as e:
            raise e
    
    def testAt(self):
        from cqlalchemy.core.builtins import now
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

            change = instance.history.at(timestamp=now())
            self.assertTrue(change is not None)
        except Exception as e:
            raise e
    
    def testUndo(self):
        from cqlalchemy.core.builtins import now
        try:
            start = now()
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
            
            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == "Amazon Kindle")

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")
            end = now()

            results = list(instance.history.span(start=start, end=end))
            self.assertTrue(len(results) == 4)
        except Exception as e:
            raise e
    


