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
import time
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, UUID
from cqlalchemy.core.commons import String, Map, List, Set, Tuple, Integer, Counter
from cqlalchemy.connection.table import Schema
from cqlalchemy.connection.cql.fluent import insert


class Base(TestCase):
    """Base class for C* related tests"""
    
    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            self.shutdown = False
            cqlalchemy.configure(
                keyspace="testfluentapi",
                servers=[
                    "localhost",
                ],
                debug=True,
                verbose=True,
            )
        except Exception as e:
            print(e)

    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            Schema.destroy()
            clear()
        except Exception as e:
            print(e)   


class TestInsertQuery(Base):
    """Test the persistence of a Map collection"""

    def testCreate(self):
        try:
            class Book(Model):
                id = UUID(primary=True)
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            key = uuid.uuid4()
            query = insert(Book)\
                        .values(id=key, name="A Tale of Two Cities", publisher="Amazon Kindle")\
                    .execute()

            book = Book.read(key)
            self.assertIsNotNone(book)
            self.assertEqual(book.name, "A Tale of Two Cities")
            self.assertEqual(book.publisher, "Amazon Kindle")
        except Exception as e:
            raise e
    
    def testCreateWithTTL(self):
        try:
            class Book(Model):
                id = UUID(primary=True)
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            key = uuid.uuid4()
            query = insert(Book).values(id=key, name="A Tale of Two Cities", publisher="Amazon Kindle")
            query.ttl(10)
            query.execute()

            book = Book.read(key)
            self.assertIsNotNone(book)
            self.assertEqual(book.name, "A Tale of Two Cities")
            self.assertEqual(book.publisher, "Amazon Kindle")

            time.sleep(10)
            book = Book.read(key)
            self.assertIsNone(book)
        except Exception as e:
            raise e
    
    def testCreateUnique(self):
        try:
            class Book(Model):
                id = UUID(primary=True)
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            key = uuid.uuid4()
            query = insert(Book)\
                .values(id=key, name="A Tale of Two Cities", publisher="Amazon Kindle")\
            .execute()
            
            query = insert(Book)\
                .values(id=key, name="A Tale of Two Cities", publisher="Barnes & Noble")\
                .unique()\
            .execute()

            book = Book.read(key)
            self.assertIsNotNone(book)
            self.assertEqual(book.name, "A Tale of Two Cities")
            self.assertEqual(book.publisher, "Amazon Kindle")
        except Exception as e:
            raise e


class TestUpdateQuery(Base):
    """Test the persistence of a Set collection"""

    def testIncrWithAtomicContext(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql import Atom
        from cqlalchemy.connection.cql.fluent import update
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                quantity = Integer(required=True)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                quantity=50,
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            with Atom() as atom:
                update(Book)\
                    .incr(quantity=1)\
                    .where(
                        r('id') == book.id
                    )\
                .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book.quantity, 51)
        except Exception as e:
            raise e
    
    def testIncrWithoutAtomicContext(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                quantity = Integer(required=True)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                quantity=50,
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            with self.assertRaises(Exception):
                update(Book)\
                    .incr(quantity=1)\
                    .where(
                        r('id') == book.id
                    )\
                .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book.quantity, 50)
        except Exception as e:
            raise e
    
    def testDecrWithAtomicContext(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql import Atom
        from cqlalchemy.connection.cql.fluent import update
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                quantity = Integer(required=True)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                quantity=50,
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            with Atom() as atom:
                update(Book)\
                    .decr(quantity=1)\
                    .where(
                        r('id') == book.id
                    )\
                .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book.quantity, 49)
        except Exception as e:
            raise e
    
    def testDecrWithoutAtomicContext(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql import Atom
        from cqlalchemy.connection.cql.fluent import update
        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                quantity = Integer(required=True)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                quantity=50,
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            with self.assertRaises(Exception):
                update(Book)\
                    .decr(quantity=1)\
                    .where(
                        r('id') == book.id
                    )\
                .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book.quantity, 50)
        except Exception as e:
            raise e

    def testIncrCounter(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.core.models import Counter
        from cqlalchemy.connection.cql.fluent import update
        try:

            Book = Counter("Book", ["quantity"])

            instance = Book.create(quantity=50)
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            update(Book)\
                .incr(quantity=1)\
                .where(
                    r('id') == book.id
                )\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book.quantity, 51)
        except Exception as e:
            raise e

    def testDecrCounter(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.core.models import Counter
        from cqlalchemy.connection.cql.fluent import update
        try:
            Book = Counter("Book", ["quantity"])
            instance = Book.create(quantity=50)
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            update(Book)\
                .decr(quantity=1)\
                .where(
                    r('id') == book.id
                )\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertEqual(book.quantity, 49)
        except Exception as e:
            raise e

    def testExists(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition": "2022-01-01",
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .add(
                    editions={
                        "2nd Edition": "2022-02-01", 
                        "3rd Edition": "2022-03-01", 
                        "4th Edition": "2022-04-01"
                    }
                )\
                .exists()\
                .where(
                    r('id') == book.id
                )\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(
                book.editions, 
                {
                    "1st Edition": "2022-01-01", 
                    "2nd Edition": "2022-02-01", 
                    "3rd Edition": "2022-03-01", 
                    "4th Edition": "2022-04-01"
                }
            )
        except Exception as e:
            raise e
    
    def testWhen(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=True)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition": "2022-01-01",
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .add(
                    editions={
                        "2nd Edition": "2022-02-01", 
                        "3rd Edition": "2022-03-01", 
                        "4th Edition": "2022-04-01"
                    }
                )\
                .when(r('publisher') == "Amazon Kindle")\
                .where(r('id') == book.id)\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(
                book.editions, 
                {
                    "1st Edition": "2022-01-01", 
                    "2nd Edition": "2022-02-01", 
                    "3rd Edition": "2022-03-01", 
                    "4th Edition": "2022-04-01"
                }
            )
        except Exception as e:
            raise e
    
    def testCannotCombineWhenAndExists(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=True)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition": "2022-01-01",
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            with self.assertRaises(Exception):
                update(Book)\
                    .add(
                        editions={
                            "2nd Edition": "2022-02-01", 
                            "3rd Edition": "2022-03-01", 
                            "4th Edition": "2022-04-01"
                        }
                    )\
                    .exists()\
                    .when(r('publisher') == "Amazon Kindle")\
                    .where(r('id') == book.id)\
                .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, {"1st Edition": "2022-01-01"})
        except Exception as e:
            raise e

    def testUpdateMap(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition": "2022-01-01",
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .set(name="A Tale of Two Cities", publisher="Amazon Kindle")\
                .set(editions={
                    "1st Edition": "2022-01-01", 
                    "2nd Edition": "2022-02-01", 
                    "3rd Edition": "2022-03-01", 
                    "4th Edition": "2022-04-01"
                })\
                .where(
                    r('id') == book.id
                )\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, {"1st Edition": "2022-01-01", "2nd Edition": "2022-02-01", "3rd Edition": "2022-03-01", "4th Edition": "2022-04-01"})
        except Exception as e:
            raise e
    
    def testUpdateMapWithRemove(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition": "2022-01-01",
                    "2nd Edition": "2022-02-01", 
                    "3rd Edition": "2022-03-01", 
                    "4th Edition": "2022-04-01"
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .remove(editions={"1st Edition",})\
                .where(
                    r('id') == book.id
                )\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, {"2nd Edition": "2022-02-01", "3rd Edition": "2022-03-01", "4th Edition": "2022-04-01"})
        except Exception as e:
            raise e

    def testUpdateMapWithAdd(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition": "2022-01-01",
                    "2nd Edition": "2022-02-01", 
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .add(editions={"3rd Edition": "2022-03-01", "4th Edition": "2022-04-01"})\
                .where(
                    r('id') == book.id
                )\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(
                book.editions, 
                {
                    "1st Edition": "2022-01-01", 
                    "2nd Edition": "2022-02-01", 
                    "3rd Edition": "2022-03-01", 
                    "4th Edition": "2022-04-01"
                }
            )
        except Exception as e:
            raise e

    def testUpdateSet(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition",
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .set(name="A Tale of Two Cities", publisher="Amazon Kindle")\
                .set(editions={"1st Edition", "2nd Edition", "3rd Edition", "4th Edition"})\
                .where(r('id') == book.id)\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, {"1st Edition", "2nd Edition", "3rd Edition", "4th Edition"})
        except Exception as e:
            raise e
    
    def testUpdateSetWithTTL(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition",
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .set(name="A Tale of Two Cities", publisher="Amazon Kindle")\
                .set(editions={"1st Edition", "2nd Edition", "3rd Edition", "4th Edition"})\
                .ttl(10)\
                .where(r('id') == book.id)\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, {"1st Edition", "2nd Edition", "3rd Edition", "4th Edition"})

            time.sleep(13)
            results = Book.objects.columns('editions').where(r('id') == book.id).get()
            self.assertIsNone(results["editions"])
        except Exception as e:
            raise e

    def testAddToSet(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition",
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .add(editions={"1st Edition", "2nd Edition", "3rd Edition"})\
                .where(
                    r('id') == book.id
                )\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, {"1st Edition", "2nd Edition", "3rd Edition"})
        except Exception as e:
            raise e

    def testRemoveFromSet(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition", "2nd Edition", "3rd Edition"
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .remove(editions={"2nd Edition", "3rd Edition"})\
                .where(
                    r('id') == book.id
                )\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, {"1st Edition"})
        except Exception as e:
            raise e

    def testUpdateList(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions=[
                    "1st Edition",
                ],
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .set(name="A Tale of Two Cities", publisher="Amazon Kindle")\
                .set(editions=["1st Edition", "2nd Edition", "3rd Edition", "4th Edition"])\
                .where(r('id') == book.id)\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, ["1st Edition", "2nd Edition", "3rd Edition", "4th Edition"])
        except Exception as e:
            raise e

    def testAppend(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions=[
                    "1st Edition",
                ],
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .append(editions=["2nd Edition", "3rd Edition", "4th Edition"])\
                .where(r('id') == book.id)\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, ["1st Edition", "2nd Edition", "3rd Edition", "4th Edition"])
        except Exception as e:
            raise e
    
    def testPrepend(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions=[
                    "4th Edition",
                ],
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .prepend(editions=["1st Edition", "2nd Edition", "3rd Edition",])\
                .where(r('id') == book.id)\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, ["1st Edition", "2nd Edition", "3rd Edition", "4th Edition"])
        except Exception as e:
            raise e

    def testInsert(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import update
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions=[
                    "4th Edition", "2nd Edition"
                ],
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            update(Book)\
                .insert(column="editions", value="1st Edition", index=0)\
                .where(r('id') == book.id)\
            .execute()

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertEqual(book.editions, ["1st Edition", "2nd Edition",])
        except Exception as e:
            raise e

class TestDeleteQuery(Base):
    """Test Fluent Interface for Delete"""

    def testDeleteListIndex(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import delete
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions=[
                    "1st Edition", "2nd Edition"
                ],
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            with self.assertRaises(Exception):
                delete(Book)\
                    .remove(column="editions", key="1st Edition")\
                    .where(r('id') == book.id)\
                .execute()

            delete(Book)\
                .remove(column="editions", index=0)\
                .where(r('id') == book.id)\
            .execute()

            book = Book.read(instance.key)
            self.assertEqual(book.editions, ["2nd Edition",])
        except Exception as e:
            raise e

    def testDeleteMapKey(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import delete
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition": "2022-01-01", 
                    "2nd Edition": "2022-02-01", 
                    "3rd Edition": "2022-03-01", 
                    "4th Edition": "2022-04-01"
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            with self.assertRaises(Exception):
                delete(Book)\
                    .remove(column="editions", index=0)\
                    .where(r('id') == book.id)\
                .execute()

            delete(Book)\
                .remove(column="editions", key="1st Edition")\
                .where(r('id') == book.id)\
            .execute()
            
            book = Book.read(instance.key)
            self.assertEqual(book.editions, {
                "2nd Edition": "2022-02-01", 
                "3rd Edition": "2022-03-01", 
                "4th Edition": "2022-04-01"
            })
        except Exception as e:
            raise e

    def testDeleteSetKey(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import delete
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition", 
                    "2nd Edition", 
                    "3rd Edition", 
                    "4th Edition"
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            with self.assertRaises(Exception):
                delete(Book)\
                    .remove(column="editions", index=0)\
                    .where(r('id') == book.id)\
                .execute()

            delete(Book)\
                .columns("editions")\
                .where(r('id') == book.id)\
            .execute()
            
            value = Book.objects.columns("editions").where(id=instance.id).get()
            self.assertIsNone(value["editions"])
        except Exception as e:
            raise e
    
    def testDeleteRow(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import delete
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition", 
                    "2nd Edition", 
                    "3rd Edition", 
                    "4th Edition"
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            delete(Book)\
                .where(r('id') == book.id)\
            .execute()
            
            value = Book.read(book.key)
            self.assertIsNone(value)
        except Exception as e:
            raise e
    
    def testDeleteRowWithExists(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import delete
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={
                    "1st Edition", 
                    "2nd Edition", 
                    "3rd Edition", 
                    "4th Edition"
                },
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            delete(Book)\
                .where(r('id') == book.id)\
                .exists()\
            .execute()
            
            value = Book.read(book.key)
            self.assertIsNone(value)
        except Exception as e:
            raise e
    
    def testDeleteRowWithConditions(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import delete
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions=[
                    "1st Edition", 
                    "2nd Edition", 
                    "3rd Edition", 
                    "4th Edition"
                ],
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            delete(Book)\
                .remove("editions", index=0)\
                .where(r('id') == book.id)\
                .when(r('publisher') == "Amazon Kindle")\
            .execute()
            
            value = Book.read(book.key)
            self.assertEqual(value.editions, [
                "2nd Edition", 
                "3rd Edition", 
                "4th Edition"
            ])
        except Exception as e:
            raise e
    
    def testDeleteRowWithWhere(self):
        from cqlalchemy.connection.functions import r
        from cqlalchemy.connection.cql.fluent import delete
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions=[
                    "1st Edition", 
                    "2nd Edition", 
                    "3rd Edition", 
                    "4th Edition"
                ],
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)

            with self.assertRaises(Exception):
                delete(Book)\
                    .remove("editions", index=0)\
                    .where(r('id') == book.id, r('publisher') == "Amazon Kindle")\
                .execute()
            
            delete(Book)\
                .remove("editions", index=0)\
                .where(r('id') == book.id)\
                .when(r('publisher') == "Amazon Kindle")\
            .execute()

            value = Book.read(book.key)
            self.assertEqual(value.editions, [
                "2nd Edition", 
                "3rd Edition", 
                "4th Edition"
            ])
        except Exception as e:
            raise e