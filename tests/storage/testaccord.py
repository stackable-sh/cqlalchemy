import uuid
import time
from unittest import TestCase, skip
from contextlib import suppress

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, Pointer, Reference, UUID
from cqlalchemy.core.commons import String, Integer
from cqlalchemy.connection.table import Schema
from cqlalchemy.connection.functions import when
from cqlalchemy.connection.cql import Atom
from cqlalchemy.connection.cql.expr import Variable, CompositionException, Operator


class Book(Model, batch=False):
    name = String(index=True, required=True)
    publisher = String(index=True, required=True)


class Author(Model, version=True):
    id = UUID(primary=True)
    name = String(index=True, required=True)
    age = Integer(required=True, index=True)
    book = Reference(Book, index=True)


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
    
    def testConditionalComparisons(self):
        try:
            atom = Atom()

            first = str(uuid.uuid4())
            second = str(uuid.uuid4())
            book = Book.create(name="A Tale of Two Cities", publisher=first)
            author = Author.create(name = "Charles Dickens", age=65, book=book)
            
            with atom:
                book_var = atom.var(Book.objects.columns("name").where(id=book.id))
                author_var = atom.var(Author.objects.columns("age").where(id=author.id))

                with atom.when(
                    book_var.name == "A Tale of Two Cities",
                    author_var.age <= 60
                ):
                    book.publisher = second 
                    book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == first)
        except Exception as e:
            raise e
    
    def testConditionalComparisons2(self):
        try:
            atom = Atom()

            first = str(uuid.uuid4())
            second = str(uuid.uuid4())
            book = Book.create(name="A Tale of Two Cities", publisher=first)
            author = Author.create(name = "Charles Dickens", age=65, book=book)
            
            with atom:
                book_var = atom.var(Book.objects.columns("name").where(id=book.id))
                author_var = atom.var(Author.objects.columns("age").where(id=author.id))

                with atom.when(
                    book_var.name == "A Tale of Two Cities",
                    author_var.age == 65
                ):
                    book.publisher = second 
                    book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == second)
        except Exception as e:
            raise e

    def testOperatorsWithNull(self):
        publisher = str(uuid.uuid4())
        second = str(uuid.uuid4())
        book = Book.create(name="A Tale of Two Cities", publisher=publisher)

        atom = Atom()
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
    
    def testConditionWithNull(self):
        try:
            first = "Stripe Press"
            second = "Google Press"
            does_not_exist = uuid.uuid4()

            book = Book.create(name="A Tale of Two Cities", publisher=first)
            self.assertIsNotNone(book)

            atom = Atom()
            with atom:
                var = atom.var(Book.objects.where(id=does_not_exist))
                with atom.when(var == None):
                    book.publisher = second 
                    book.save()

            instance = Book.read(book.key)
            self.assertEqual(book.publisher, second)
        except Exception as e:
            raise e
    
    def testConditionWithNotNull(self):
        try:
            first = "Stripe Press"
            second = "Google Press"

            book = Book.create(name="A Tale of Two Cities", publisher=first)
            self.assertIsNotNone(book)

            atom = Atom()
            with atom:
                var = atom.var(Book.objects.where(id=book.id))
                with atom.when(var != None):
                    book.publisher = second 
                    book.save()

            instance = Book.read(book.key)
            self.assertEqual(book.publisher, second)
        except Exception as e:
            raise e
