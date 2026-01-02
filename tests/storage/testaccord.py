import uuid
from unittest import TestCase, skip
from contextlib import suppress

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, Pointer
from cqlalchemy.core.commons import String
from cqlalchemy.connection.table import Schema
from cqlalchemy.connection.functions import when
from cqlalchemy.connection.cql.atom import Atom
from cqlalchemy.connection.cql.expr import Variable, CompositionException, Operator


class Book(Model, batch=False):
    name = String(index=True, required=True)
    publisher = String(index=True, required=True)


class Author(Model, version=True):
    name = String(index=True, required=True)
    publisher = String(index=True, required=True)


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            self.shutdown = False
            cqlalchemy.configure(
                keyspace="TransactionTest",
                servers=[
                    "localhost",
                ],
                debug=True,
                verbose=True,
            )
            Schema.put(Book)
            Schema.put(Author)
        except Exception as e:
            pass 

    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            if not self.shutdown:
                self.shutdown = True
            Schema.destroy()
            clear()
        except Exception as e:
            raise e


class TestAtom(Base):
    """Test the persistence functionality of Model within an Atom"""

    def testWithoutConditions(self):
        try:
            atom = Atom()
            publisher = str(uuid.uuid4())
            with atom:
                book = Book.create(name="A Tale of Two Cities", publisher=publisher)
            self.assertIsNotNone(book)
            
            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertTrue(book.name == "A Tale of Two Cities")
            self.assertTrue(book.publisher == publisher)
        except Exception as e:
            raise e

    def testOperators(self):
        with suppress(CompositionException):
            publisher = str(uuid.uuid4())
            book = Book.create(name="A Tale of Two Cities", publisher=publisher)

            atom = Atom()
            with atom:
                var = atom.var(book)
                attr = var.name
                self.assertTrue(isinstance(attr, Variable))
                self.assertTrue(isinstance(attr._entity_, Book))
                self.assertEqual(attr._attribute_, "name")
                self.assertTrue(isinstance(var.name == "A Tale of Two Cities", Operator))

    def testConditions(self):
        try:
            atom = Atom()

            publisher = str(uuid.uuid4())
            second = str(uuid.uuid4())
            book = Book.create(name="A Tale of Two Cities", publisher=publisher)
            
            with atom:
                var = atom.var(book)
                with atom.when(var.name == "A Tale of Two Cities"):
                    book.publisher = second 
                    book.save()

            self.assertIsNotNone(book)
            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertTrue(book.name == "A Tale of Two Cities")
            self.assertTrue(book.publisher == second)
        except Exception as e:
            raise e
    
    def testOperatorsWithNull(self):
        publisher = str(uuid.uuid4())
        second = str(uuid.uuid4())
        book = Book.create(name="A Tale of Two Cities", publisher=publisher)

        atom = Atom()
        #with suppress(CompositionException):
        var = atom.var(book)
        self.assertIsNone(var._attribute_)
        self.assertTrue(isinstance(var._entity_, Book))
        with suppress(CompositionException):
            attr = (var.name != None)
    
    def testVariablesWithNull(self):
        publisher = str(uuid.uuid4())
        second = str(uuid.uuid4())
        book = Book.create(name="A Tale of Two Cities", publisher=publisher)

        atom = Atom()
        var = atom.var(book)
        attr = (var == None)
        left, right = attr.convert()
        self.assertTrue(isinstance(attr, Operator))
        self.assertTrue(isinstance(attr.entity, Book))    
        self.assertEqual(left, var._name_)
        self.assertEqual(right, None)
        attr.validate()
        self.assertEqual(str(attr), f"{left} IS NULL")
    
    @skip("Cassandra Accord Bug: #1 - LET var = (SELECT * FROM Table WHERE id = ?) should not return NULL if the table exists")
    def testConditionWithNull(self):
        try:
            
            publisher ="1"
            second = "2"
            book = Book.create(name="A Tale of Two Cities", publisher=publisher)
            print("1:", book.publisher)

            self.assertIsNotNone(book)
            pointer = Pointer.create(book)
            
            atom = Atom()
            with atom:
                var = atom.var(pointer)
                with atom.when(var == None):
                    # This block should not be executed.
                    book.publisher = second 
                    book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertTrue(book.name == "A Tale of Two Cities")
            print("2: ", book.publisher)
            self.assertEqual(book.publisher, publisher)
        except Exception as e:
            raise e
    
    @skip("Cassandra Accord Bug: #2 - LET var = (SELECT * FROM Table WHERE id = ?) should not return NULL if the table exists")
    def testConditionWithNull2(self):
        try:
            publisher = "1"
            second = "2"
            book = Book.create(name="A Tale of Two Cities", publisher=publisher)
            self.assertIsNotNone(book)
            pointer = Pointer.create(book)
            
            atom = Atom()
            with atom:
                var = atom.var(
                    Book.objects.columns("name").where(id=book.id)
                )
                with atom.when(var.name == None):
                    # This block should not be executed.
                    book.publisher = second 
                    book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertTrue(book.name == "A Tale of Two Cities")
            self.assertEqual(book.publisher, publisher)
        except Exception as e:
            raise e
    
    