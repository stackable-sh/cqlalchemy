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
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            self.shutdown = False
            Schema.clear()
            cqlalchemy.configure(
                keyspace="ExpandoTest",
                servers=[
                    "localhost",
                ],
                debug=False,
                verbose=True,
            )
        except Exception as e:
            print(e)

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


class TestExpando(Base):

    def testTable(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.core.models import Table, Expando

        Book = Table("Book", Expando)
        self.assertTrue(issubclass(Book, Expando))

    def testTableOptions(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.time import days
        from cqlalchemy.core.models import Table, Expando

        Book = Table("Book", Expando, keyspace="Kindle", version=True, expire=days(30))
        book = Book()
        self.assertTrue(issubclass(Book, Expando))
        self.assertTrue(Book.__options__.get("version"))
        self.assertTrue(book.keyspace() == "kindle")
        self.assertTrue(book.expire == days(30))

    def testCreate(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testNew(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Expando.new("Book")
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testCreateHybrid(self):
        from cqlalchemy.core.models import Table, Expando

        try:

            class Book(Expando):
                author = String(index=True)

            book = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                author="Charles Dickens",
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            book = Book.refresh(book)
            self.assertTrue(book["author"] == "Charles Dickens")

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testCreateIfNotExists(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
            book = Book.create(
                name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testRead(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
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
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            instance = Book.read(book.key)
            self.assertEqual(instance, book)

            book["publisher"] = "Barnes & Noble"
            book.save()
            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEqual(instance["publisher"], "Barnes & Noble")

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testHas(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")

            instance = Book.read(book.key)
            book["publisher"] = "Barnes & Noble"
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertTrue(instance.has("publisher"))
            self.assertTrue(instance.has(value="Barnes & Noble"))
            self.assertTrue(instance.has(entry=("publisher", "Barnes & Noble")))

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpdateWithTTL(self):
        import time
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            book.put({"author": "Charles Dickens", "ttl": 3})
            instance = Book.read(book.key)
            self.assertEqual(instance.get("author")[0], "Charles Dickens")
            time.sleep(5)

            book = Book.refresh(instance)
            self.assertIsNone(book.get("author")[0])

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpsert(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            var = book.id
            found = Book.upsert(
                id=var, name="A Tale of Two Cities", publisher="Barnes & Noble"
            )
            self.assertEqual(book, found)
            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEqual(instance["publisher"], "Barnes & Noble")

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testQueryValue(self):
        from cqlalchemy.core.models import Table, Expando
        from cqlalchemy.connection.cql import Level

        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            with Level.All:
                found = Book.objects.contains(value="A Tale of Two Cities").get()
            self.assertEqual(book, found)
            self.assertEqual(found["publisher"], "Amazon Kindle")

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testQueryKey(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            found = Book.objects.contains(key="publisher").get()
            self.assertEqual(book, found)
            self.assertEqual(found["publisher"], "Amazon Kindle")

        except Exception as e:
            raise e
        finally:
            self.tearDown()
