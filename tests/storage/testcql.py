import uuid
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String, Float, Integer
from cqlalchemy.connection.cql import CqlQueryException
from cqlalchemy.options import clear
from cqlalchemy.connection.functions import LTE, max, writetime
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            cqlalchemy.configure(
                keyspace="CQLTest",
                servers=[
                    "localhost",
                ],
                debug=False,
                verbose=False,
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


class TestCqlQuery(Base):
    """Tests for the Builder object"""

    def testCreate(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        book = Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        self.assertIsNotNone(book)

    def testRead(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        book = Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )

        found = Book.read(key)
        self.assertEqual(book, found)
        for name in ["isbn", "publisher", "name", "price"]:
            self.assertTrue(found[name] == book[name])

    def testWhere(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        book = Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )

        query = Book.objects.where(
            publisher="Simon & Schuster Co", price=LTE(10)
        ).execute(filter=True)
        found = query.get()
        self.assertEqual(book, found)

    def testGroup(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        Book.create(
            isbn=uuid.uuid4(),
            publisher="Simon & Schuster Co",
            name="War and Peace",
            price=10.0,
        )
        Book.create(
            isbn=uuid.uuid4(),
            publisher="Simon & Schuster Co",
            name="Atlas Shrugged",
            price=10.0,
        )
        Book.create(
            isbn=uuid.uuid4(),
            publisher="Simon & Schuster Co",
            name="Marienbad My Love: Vol. 1",
            price=10.0,
        )
        Book.create(
            isbn=uuid.uuid4(),
            publisher="Simon & Schuster Co",
            name="Shangai",
            price=10.0,
        )
        Book.create(
            isbn=uuid.uuid4(),
            publisher="Simon & Schuster Co",
            name="Poor Fellow My Country",
            price=10.0,
        )
        Book.create(
            isbn=uuid.uuid4(),
            publisher="Simon & Schuster Co",
            name="A Suitable Boy",
            price=10.0,
        )

        query = (
            Book.objects.columns("name", "publisher")
            .where(publisher="Simon & Schuster Co", price=LTE(10))
            .group("publisher")
            .execute(filter=True)
        )
        results = list(query.all())
        self.assertTrue(len(results) == 6)

    def testDistinct(self):
        class Book(Model):
            isbn = String(
                primary=True,
                composite=[
                    "publisher",
                ],
            )
            publisher = String(index=True, key=True)
            author = String(key=True)
            name = String(required=True, index=True)
            price = Float(index=True, required=True, static=True)

        key = str(uuid.uuid4())
        book = Book.create(
            isbn=key,
            publisher="Simon & Schuster Co",
            name="War and Peace",
            author="Leo Tolstoy",
            price=10.0,
        )
        # You can only filter on partition keys or static columns when you use distinct
        with self.assertRaises(CqlQueryException):
            Book.objects.where(
                author="Leo Tolstoy", name="War & Peace"
            ).distinct().execute(filter=True)

        query = Book.objects.distinct().where(publisher="Simon & Schuster Co")
        query = query.execute(filter=True)
        results = query.get()
        self.assertTrue(results["publisher"] == "Simon & Schuster Co")

    def testOrder(self):
        class Book(Model):
            isbn = String(key=True, primary=True)
            publisher = String(index=True)
            name = String(required=True, key=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="Anna Karenina", price=8.99
        )

        query = (
            Book.objects.where(price=LTE(10), isbn=key)
            .order("name", asc=True)
            .execute(filter=True)
        )
        results = list(query.all())
        self.assertTrue(len(results) == 2)

    def testLimit(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )

        query = Book.objects.where(price=LTE(10)).limit(1).execute(filter=True)
        results = list(query.all())
        self.assertTrue(len(results) == 1)

    def testCount(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(isbn=key2, name="Art of Persuasion", price=8.99)

        query = Book.objects.count()
        self.assertTrue(query.get(), 2)

        query = Book.objects.count("publisher")
        self.assertTrue(query.get() == 1)

    def testAvg(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99
        )

        result = Book.objects.avg("price").get()
        self.assertTrue(result["price"])

    def testMin(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99
        )

        result = Book.objects.min("price").get()
        self.assertTrue(result["price"])

    def testMax(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99
        )

        result = Book.objects.max("price").get()
        self.assertTrue(result["price"] == 10.0)

    def testSum(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99
        )

        result = Book.objects.sum("price").get()
        self.assertTrue(result["price"])

    def testColumns(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(index=True, required=True)
            price = Integer(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10
        )
        Book.create(
            isbn=key2,
            publisher="Simon & Schuster Co",
            name="Art of Persuasion",
            price=8,
        )

        query = (
            Book.objects.columns("name", "isbn", "publisher")
            .where(publisher="Simon & Schuster Co")
            .execute(filter=True)
        )
        result = list(query.all())
        self.assertTrue(len(result) == 2)

    def testTTLAndWriteTime(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99
        )

        query = (
            Book.objects.columns(writetime("name"))
            .where(price=LTE(20.0))
            .execute(filter=True)
        )
        result = query.get()
        self.assertTrue(result["name"])

    def testTTL(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99
        )

        result = Book.objects.ttl("name").get()
        self.assertIsNone(result["name"])

    def testWriteTime(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99
        )

        result = Book.objects.writetime("name").get()
        self.assertTrue(result["name"])

    def testAll(self):
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(
            isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0
        )
        Book.create(
            isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99
        )

        results = list(Book.objects.all())
        self.assertTrue(len(results), 2)
