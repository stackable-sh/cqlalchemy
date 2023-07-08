import traceback
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import keyspace, clear
from cqlalchemy.core.models import Model, UUID
from cqlalchemy.core.commons import String
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure home globally"""
        try:
            self.shutdown = False
            cqlalchemy.configure(
                keyspace="Test",
                servers=[
                    "localhost",
                ],
                debug=False,
            )
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


class TestUpdateSchema(Base):
    """Special Case of Schema Test"""

    def initialize(self):
        """Set the stage for an update to occur"""
        space = keyspace()
        Schema.create_keyspace(space)

        class Book(Model):
            name = String(index=True, required=True)

        entity = Book(name="A Tale of Two Cities")
        Schema.create_table(entity)

    def testUpdate(self):
        """Tests the update of an Entity that exists on C*"""
        try:
            self.initialize()
            Schema.clear()

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            entity = Book(name="A Tale of Two Cities", publisher="Amazon Kindle")
            Schema.update_table(entity)
            self.assertTrue(Book.table() in Schema.entities)
        except Exception as e:
            traceback.print_exc()
            raise e
        finally:
            self.tearDown()


class TestSchema(Base):
    """Behavioral Tests for Schema"""

    def testKeyspace(self):
        """Tests keyspace creation"""
        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

    def testCreate(self):
        """Tests Entity table creation"""
        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)

        entity = Book(name="A Tale of Two Cities")
        Schema.create_table(entity)
        self.assertTrue(Book.table() in Schema.entities)

    def testGet(self):
        """Tests Entity table retreival"""
        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)

        entity = Book(name="A Tale of Two Cities")
        Schema.create_table(entity)
        self.assertTrue(Book.table() in Schema.entities)
        kind = Schema.get(entity.table())
        self.assertEqual(kind, Book)

    def testIndex(self):
        """Tests Entity index creation"""
        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)

        entity = Book(name="A Tale of Two Cities")
        Schema.create_table(entity)
        self.assertTrue(Book.table() in Schema.entities)
        Schema.create_indexes(entity)
        self.assertTrue(len(Schema.indexes[entity]))

    def testStatic(self):
        """Tests creation of static attributes"""
        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            id = UUID(primary=True)
            name = String(index=True, required=True)
            isbn = String(key=True)
            publisher = String(index=True, static=True, required=True)

        entity = Book(
            name="A Tale of Two Cities",
            publisher="Amazon Kindle",
            isbn="1e5e72ee-2c74-4ec0-aea4-ac95530e43a4",
        )
        Schema.create_table(entity)
        self.assertTrue(Book.table() in Schema.entities)

    def testComposite(self):
        """Tests creation of Entity with composite key"""
        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            id = UUID(primary=True, composite=["isbn"])
            name = String(index=True, required=True)
            isbn = String(key=True)
            publisher = String(index=True, required=True)

        entity = Book(
            name="A Tale of Two Cities",
            publisher="Amazon Kindle",
            isbn="1e5e72ee-2c74-4ec0-aea4-ac95530e43a4",
        )
        Schema.create_table(entity)
        self.assertTrue(Book.table() in Schema.entities)

    def testCompositeAndClustering(self):
        """Tests creation of Entity with composite and clustering keys"""
        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            id = UUID(primary=True, composite=["isbn"])
            name = String(index=True, required=True)
            isbn = String(key=True)
            author = String(key=True, order="DESC")
            publisher = String(index=True, required=True)

        entity = Book(
            name="A Tale of Two Cities",
            isbn="1e5e72ee-2c74-4ec0-aea4-ac95530e43a4",
            author="Charles Dickens",
            publisher="Amazon Kindle",
        )
        Schema.create_table(entity)
        self.assertTrue(Book.table() in Schema.entities)

    def testCreate(self):
        """Tests whether the Schema.create behaves correctly"""
        space = keyspace()

        class Book(Model):
            id = UUID(primary=True, composite=["isbn"])
            name = String(index=True, required=True)
            isbn = String(key=True)
            author = String(key=True)
            publisher = String(index=True, required=True)

        entity = Book(
            name="A Tale of Two Cities",
            isbn="1e5e72ee-2c74-4ec0-aea4-ac95530e43a4",
            author="Charles Dickens",
            publisher="Amazon Kindle",
        )
        Schema.create(entity)
        self.assertTrue(Book.table() in Schema.entities)
        self.assertTrue(len(Schema.indexes[entity]))
        self.assertTrue(space in Schema.keyspaces)
