import uuid
from unittest import TestCase, skip, expectedFailure

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, UUID
from cqlalchemy.core.commons import String, Map, List, Set, Tuple, Integer
from cqlalchemy.connection.table import Schema
from cqlalchemy.connection.cql.fluent import update, delete
from cqlalchemy.exceptions import IsolatedStaticFieldException

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


class TestObjectMapper(Base):
    """Tests whether we can catch errors at the model level before we get to C*"""

    def testNormalUpdate(self):
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
            book.name = "A Tale of Two Cities II"
            book.save()
            self.assertEqual(book.publisher, "Barnes & Noble")
            self.assertEqual(book.name, "A Tale of Two Cities II")

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEqual(instance["publisher"], "Barnes & Noble")
            self.assertEqual(instance["name"], "A Tale of Two Cities II")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpdateMultipleColumnsWithStatic(self):
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
    
    def testUpdateSingleStaticColumn(self):
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
            with self.assertRaises(Exception):
                book.save()
            
            new = Book.refresh(book)
            self.assertEqual(new.owner, "Jeff Bezos")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpsertWithStatic(self):
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
            with self.assertRaises(Exception):
                found = Book.upsert(
                    id=var, 
                    author="Mark Twain", 
                    owner="Beff Jezos"
                )
            
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testDeleteWithStatic(self):
        """Tests that we can delete an existing C* object in place"""
        from cqlalchemy.connection.cql import Level

        try:

            class Book(Model):
                id = UUID(primary=True)
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                author = String(key=True)
                owner = String(static=True)

            book = Book.create(
                name="A Tale of Two Cities", 
                publisher="Amazon Kindle",
                author="Mark Twain",
                owner="Jeff Bezos"
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            with self.assertRaises(Exception):
                del book.owner
                book.save()
        except Exception as e:
            raise e
        finally:
            self.tearDown()


class TestFluentAPI(Base):
    """Tests whether we can catch errors at the model level before we get to C*"""

    def testNormalUpdate(self):
        """Tests that we can update an entity on C*"""
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            update(Book)\
                .set(
                    publisher="Barnes & Noble", 
                    name="A Tale of Two Cities II"
                )\
                .where(id=book.id)\
            .execute()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEqual(instance["publisher"], "Barnes & Noble")
            self.assertEqual(instance["name"], "A Tale of Two Cities II")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    
    def testUpdateSingleStaticColumn(self):
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
            with self.assertRaises(IsolatedStaticFieldException):
                update(Book).set(owner="Beff Jezos").where(id=book.id).execute()
            
            new = Book.refresh(book)
            self.assertEqual(new.owner, "Jeff Bezos")
        except Exception as e:
            raise e
        finally:
            self.tearDown()


    def testDeleteWithStatic(self):
        """Tests that we can delete an existing C* object in place"""
        from cqlalchemy.connection.cql import Level

        try:

            class Book(Model):
                id = UUID(primary=True)
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                author = String(key=True)
                owner = String(static=True)

            book = Book.create(
                name="A Tale of Two Cities", 
                publisher="Amazon Kindle",
                author="Mark Twain",
                owner="Jeff Bezos"
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            with self.assertRaises(IsolatedStaticFieldException):
                delete(Book).columns("owner").where(id=book.id).execute()
            
            new = Book.refresh(book)
            self.assertEqual(new.owner, "Jeff Bezos")
        except Exception as e:
            raise e
        finally:
            self.tearDown()