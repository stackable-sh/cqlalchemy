import uuid
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String, Float
from cqlalchemy.connection.cql import Level
from cqlalchemy.connection.functions import LTE, max, ttl, writetime
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    '''Base class for C* related tests'''

    def setUp(self):
        '''Configure home globally'''
        try:
            cqlalchemy.configure(keyspace="Test", servers=["localhost",], debug=True, verbose=True)
        except Exception as e:
            print(e)
            
    def tearDown(self):
        '''Release resources that have been allocated'''
        try:
            Schema.dropKeyspace()
        except Exception as e:
            print(e)


@skip
class TestCqlQuery(Base):
    '''Tests for the AutoCqlQuery object'''
    

    def testCreate(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        book = Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        self.assertIsNotNone(book)
        

    def testRead(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        book = Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)

        found = Book.read(key)
        self.assertEqual(book, found)
        for name, value in book.items():
            self.assertTrue(found[name] == value)


    def testWhere(self):
        """Use case and API verification for CqlQuery & Model"""
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        book = Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)

        query = Book.objects\
                .where(publisher="Simon & Schuster Co", price=LTE(10))\
            .execute(filter=True)
        
        found = query.one()
        self.assertEqual(book, found)
    

    def testDistinct(self):
        """Use case and API verification for CqlQuery & Model"""
        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        book = Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)

        query = Book.objects\
                    .where(publisher="Simon & Schuster Co", price=LTE(10))\
                    .distinct("isbn")\
                .execute(filter=True)
        found = query.get()
        self.assertEqual(book, found)


    def testOrder(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        book = Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)

        results = Book.objects\
                    .where(price=LTE(10))\
                    .order("name", asc=True)\
                .execute(filter=True)
        self.assertTrue(len(results) == 2)
    

    def testLimit(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key = str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)

        results = Book.objects\
                    .where(price=LTE(10))\
                    .order("name", asc=True)\
                    .limit(1)\
                .execute(filter=True)
        self.assertTrue(len(results) == 1)

    def testCount(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects.count()
        self.assertTrue(query.first(), 2)

        query = Book.objects.count(publisher="Simon & Schuster Co")
        self.assertTrue(query.first() == 1)
    

    def testAvg(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects.avg("price")
        query.execute()
        self.assertTrue(query.first()["price"] == 9.495)
    
    def testMin(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects.min("price")
        query.execute()
        self.assertTrue(query.first()["price"] == 8.99)
    
    def testMax(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects.max("price")
        query.execute()
        self.assertTrue(query.first()["price"] == 10.0)
    
    def testSum(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects.sum("price")
        query.execute()
        self.assertTrue(query.first()["price"] == 18.99)
    
    def testColumns(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects\
                    .columns("name", "isbn", "publisher", max("price"))\
                    .where(price=LTE(20.0))\
                .execute()
        result = query.first()
        self.assertTrue(result["price"] == 10.0)
        self.assertTrue(result["name"] == "War and Peace")
        self.assertTrue(result["publisher"] == "Simon & Schuster Co")
    
    def testTTLAndWriteTime(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects\
                    .columns(ttl("name"), writetime("isbn"))\
                    .where(price=LTE(20.0))\
                .execute()
        
        result = query.first()
        self.assertTrue(result["name"])
        self.assertTrue(result["isbn"])

    def testTTL(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects.ttl("name")
        query.execute()
        
        result = query.first()
        self.assertTrue(result["name"])
    
    def testWriteTime(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        query = Book.objects.writetime("name")
        query.execute()

        result = query.first()
        self.assertTrue(result["name"])

    def testAll(self):
        """Use case and API verification for CqlQuery & Model"""

        class Book(Model):
            isbn = String(key=True)
            publisher = String(index=True)
            name = String(required=True)
            price = Float(index=True, required=True)

        key, key2 = str(uuid.uuid4()), str(uuid.uuid4())
        Book.create(isbn=key, publisher="Simon & Schuster Co", name="War and Peace", price=10.0)
        Book.create(isbn=key2, publisher="Barnes & Noble", name="Art of Persuasion", price=8.99)

        results = Book.objects.all()
        self.assertTrue(len(results), 2)

    
            
