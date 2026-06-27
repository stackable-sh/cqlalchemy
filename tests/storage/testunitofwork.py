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

import uuid
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.connection.cql import Session
from cqlalchemy.core.models import Model, Reference
from cqlalchemy.core.commons import String, Map
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    """Base class for C* related tests"""

    @classmethod
    def keyspace(cls):
        return f"{cls.__name__}Session"
    
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

class TestSession(Base):
    """Tests the Unit of Work pattern"""

    def testAdd(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            session = Session()
            session.add(instance)
            session.save()

            self.assertTrue(session.contains(instance))

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
        except Exception as e:
            raise e
    
    def testTransaction(self):
        from cqlalchemy.exceptions import InvalidatedModelError
        from cqlalchemy.connection.cql import Atom
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            session = Session()
            session.add(instance)
            self.assertTrue(session.contains(instance))
            self.assertTrue(session.dirty)
            
            with Atom() as atom:
                session.save()

            self.assertTrue(session.contains(instance))
            with self.assertRaises(InvalidatedModelError):
                instance.saved()

            found = session.get(instance.key)
            self.assertIsNotNone(found)
            self.assertTrue(found.saved())

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
        except Exception as e:
            raise e


    def testDelete(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            session = Session()
            session.add(instance)
            session.save()
            self.assertTrue(session.contains(instance))
            self.assertIsNotNone(instance.key)

            book = session.get(instance.key)
            session.delete(book)
            session.save()

            self.assertFalse(session.contains(book))
            self.assertIsNone(Book.read(instance.key))
        except Exception as e:
            raise e
    
    def testDirty(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            session = Session()
            session.add(instance)
            session.save()

            self.assertFalse(session.dirty)
            self.assertTrue(session.contains(instance))

            instance.name = "A New Name"

            self.assertTrue(session.dirty)
            session.save()
            self.assertFalse(session.dirty)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
        except Exception as e:
            raise e

    def testRemove(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            session = Session()
            session.add(instance)
            session.save()

            book = session.get(instance.key)
            self.assertTrue(session.contains(book))

            session.expunge(instance)
            self.assertFalse(session.contains(instance))
        except Exception as e:
            raise e

    def testContextManager(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            
            session = Session()
            with session:
                session.add(instance)
                session.save()
                book = session.get(instance.key)
                self.assertTrue(session.contains(book))
                session.expunge(instance)
                self.assertFalse(session.contains(instance))
    
            self.assertTrue(session.closed)
            with self.assertRaises(Exception):
                session.add(instance)

            with self.assertRaises(Exception):
                session = Session()
                with session:
                    self.assertFalse(session.closed)

                    instance = Book(
                        name="Huckleberry Finn",
                        publisher="Amazon Kindle",
                        editions={"1st Edition": str(uuid.uuid4())},
                    )
                    session.add(instance)
        except Exception as e:
            raise e

    def testGetExistingEntity(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            session = Session()
            session.add(instance)
            session.save()

            book = session.get(instance.key)
            self.assertTrue(session.contains(book))
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.editions)
        except Exception as e:
            raise e

    def testExplicitFlush(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            session = Session()
            session.add(instance)
            session.flush()

            book = session.get(instance.key)
            self.assertTrue(session.contains(book))
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.editions)
        except Exception as e:
            raise e
    
    def testImplicitFlush(self):
        from cqlalchemy.connection.cql import Level
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            session = Session()
            session.add(instance)
            session.save()

            book = session.get(instance.key)
            self.assertTrue(session.contains(book))
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.editions)

            self.assertEqual(instance.key, book.key)
            session.delete(instance.key)
            instance = session.cache(instance.key) # triggers a flush
            self.assertIsNone(instance)
            self.assertFalse(session.contains(book))
        except Exception as e:
            raise e

    def testGetFreshEntity(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            instance.save()

            session = Session()
            book = session.get(instance.key)

            self.assertTrue(session.contains(book))
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.editions)
        except Exception as e:
            raise e
    
    def testRefresh(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            instance.save()

            session = Session()
            book = session.get(instance.key)

            self.assertTrue(session.contains(book))
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.editions)

            found = session.refresh(book)
            self.assertIsNotNone(found)
            self.assertTrue(session.contains(found))
            self.assertEqual(book.key, found.key)
        except Exception as e:
            raise e

    def testQuery(self):
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            Schema.refresh(Book)

            instance = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            instance.save()

            session = Session()
            book = session.query(Book).where(name="A Tale of Two Cities").get()

            self.assertTrue(session.contains(book))
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.editions)
        except Exception as e:
            raise e
    
    def testReference(self):
        try:
            class Author(Model):
                name = String(index=True, required=True)

            
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)
                author = Reference(Author)

            Schema.refresh(Book)
            Schema.refresh(Author)

            author = Author(name="Charles Dickens")
            book = Book(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
                author=author,
            )

            session = Session()
            session.add(author)
            session.add(book)
            session.save()

            self.assertTrue(session.contains(book))
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.editions)
            self.assertIsNotNone(book.author)
            self.assertTrue(book.author.saved())
            self.assertTrue(session.contains(author))
            self.assertTrue(session.contains(book.author))
            self.assertIsNotNone(author)
            self.assertTrue(author.saved())
        except Exception as e:
            raise e