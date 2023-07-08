import uuid
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String, Map, List, Set
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
                debug=True,
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
                clear()
        except Exception as e:
            raise e


class TestMap(Base):
    """Test the persistence of a Map collection"""

    def testCreate(self):
        """Tests that we can create an Entity with a Map on C*"""
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
        except Exception as e:
            raise e

    def testUpdate(self):
        """Tests that we can udpate an Entity with a Map on C*"""
        from cqlalchemy.core.differ import changed, changes

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions["2nd Edition"] = str(uuid.uuid4())
            book.editions["3rd Edition"] = str(uuid.uuid4())
            book.editions["4th Edition"] = str(uuid.uuid4())
            book.save()
            self.assertTrue(len(book.editions) == 4)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 4)
        except Exception as e:
            raise e

    def testDelete(self):
        """Tests that we can udpate an Entity with a Map on C*"""
        from cqlalchemy.core.differ import changed, changes

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions["2nd Edition"] = str(uuid.uuid4())
            book.editions["3rd Edition"] = str(uuid.uuid4())
            book.editions["4th Edition"] = str(uuid.uuid4())
            book.save()
            self.assertTrue(len(book.editions) == 4)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 4)

            del book.editions["2nd Edition"]
            del book.editions["3rd Edition"]
            book.save()
            self.assertTrue(len(book.editions) == 2)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 2)
        except Exception as e:
            raise e

    def testIndexAll(self):
        from cqlalchemy.core.differ import changed, changes

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=True)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)
        except Exception as e:
            raise e

    def testIndexKey(self):
        from cqlalchemy.core.models import Index

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=Index.KEYS)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)
        except Exception as e:
            raise e

    def testIndexValues(self):
        from cqlalchemy.core.models import Index

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=Index.VALUES)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": str(uuid.uuid4())},
            )

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)
        except Exception as e:
            raise e


class TestSet(Base):
    """Test the persistence of a Set collection"""

    def testCreate(self):
        """Tests that we can create an Entity with a Map on C*"""
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
        except Exception as e:
            raise e

    def testUpdate(self):
        """Tests that we can udpate an Entity with a Map on C*"""
        from cqlalchemy.core.differ import changed, changes

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
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions.add("2nd Edition")
            book.editions.add("3rd Edition")
            book.editions.add("4th Edition")
            book.save()
            self.assertTrue(len(book.editions) == 4)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 4)
        except Exception as e:
            raise e

    def testDelete(self):
        """Tests that we can udpate an Entity with a Map on C*"""
        from cqlalchemy.core.differ import changed, changes

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
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions.add("2nd Edition")
            book.save()
            self.assertTrue(len(book.editions) == 2)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 2)

            book.editions.remove("2nd Edition")
            book.save()
            self.assertTrue(len(book.editions) == 1)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 1)
        except Exception as e:
            raise e

    def testIndexAll(self):
        from cqlalchemy.core.differ import changed, changes

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String, index=True)

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
            self.assertTrue(len(book.editions) == 1)
        except Exception as e:
            raise e

    def testIndexValues(self):
        from cqlalchemy.core.models import Index

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String, index=Index.VALUES)

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
            self.assertTrue(len(book.editions) == 1)
        except Exception as e:
            raise e

    def testIndexKeys(self):
        from cqlalchemy.core.models import Index
        from cqlalchemy.connection.table import SchemaError

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Set(String, index=Index.KEYS)

            with self.assertRaises(SchemaError):
                instance = Book.create(
                    name="A Tale of Two Cities",
                    publisher="Amazon Kindle",
                    editions={
                        "1st Edition",
                    },
                )
        except Exception as e:
            raise e


class TestList(Base):
    """Test the persistence of a List collection"""

    def testCreate(self):
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
        except Exception as e:
            raise e

    def testAppend(self):
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

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions.append("2nd Edition")
            book.editions.append("3rd Edition")
            book.editions.append("4th Edition")
            book.save()
            self.assertTrue(len(book.editions) == 4)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 4)
        except Exception as e:
            raise e

    def testPrepend(self):
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

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions.prepend("2nd Edition")
            book.editions.prepend("3rd Edition")
            book.editions.prepend("4th Edition")
            book.save()
            self.assertTrue(len(book.editions) == 4)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 4)
        except Exception as e:
            raise e

    def testExtend(self):
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

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions.extend(["2nd Edition", "3rd Edition", "4th Edition"])
            book.save()
            self.assertTrue(len(book.editions) == 4)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 4)
        except Exception as e:
            raise e

    def testDelete(self):
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
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions.append("2nd Edition")
            book.editions.append("3rd Edition")
            book.editions.append("4th Edition")
            book.save()
            self.assertTrue(len(book.editions) == 4)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 4)

            del book.editions[0]
            del book.editions[1]
            book.save()
            self.assertTrue(len(book.editions) == 2)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 2)
        except Exception as e:
            raise e

    def testRandomWalk(self):
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
            self.assertTrue(len(book.editions) == 1)

            book.publisher = "Barnes & Noble"
            book.editions.append("2nd Edition")
            book.editions.append("3rd Edition")
            book.editions.append("4th Edition")
            book.editions.extend(["5th Edition", "6th Edition"])
            book.editions.prepend("Draft Edition")
            book.save()
            self.assertTrue(len(book.editions) == 7)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 7)

            del book.editions[2]
            del book.editions[3]
            book.editions[0] = "Manuscript"
            book.save()
            self.assertTrue(len(book.editions) == 5)

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertTrue(len(book.editions) == 5)
        except Exception as e:
            raise e

    def testIndexAll(self):
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String, index=True)

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
            self.assertTrue(len(book.editions) == 1)
        except Exception as e:
            raise e

    def testIndexValues(self):
        from cqlalchemy.core.models import Index

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String, index=Index.VALUES)

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
            self.assertTrue(len(book.editions) == 1)
        except Exception as e:
            raise e

    def testIndexKeys(self):
        from cqlalchemy.core.models import Index
        from cqlalchemy.connection.table import SchemaError

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String, index=Index.KEYS)

            with self.assertRaises(SchemaError):
                instance = Book.create(
                    name="A Tale of Two Cities",
                    publisher="Amazon Kindle",
                    editions=[
                        "1st Edition",
                    ],
                )
        except Exception as e:
            raise e


class TestModel(Base):
    """Test the persistence functionality of Model"""

    def testCreate(self):
        """Tests that we can create an entity on C*"""
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testNormalBatchContext(self):
        """Tests whether the Batch Context object works as designed"""
        from cqlalchemy.connection.cql import Batch

        try:

            class Book(Model):
                name = String(index=True, required=True)
                author = String(index=True, required=True)

            results, output = [], []
            with Batch() as b:
                a = Book.create(name="The Great Gasby", author="F. Scott Fitzgerald")
                b = Book.create(
                    name="The Adventures of Huckleberry Finn", author="Mark Twain"
                )
                c = Book.create(name="To Kill a Mockingbird", author="Harper Lee")
                results.extend([a, b, c])

            for book in results:
                found = Book.read(book.key)
                output.append(found)
            self.assertTrue(len(output) == 3)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testRead(self):
        """Tests that we can create an entity on C*"""
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

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
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEquals(instance["publisher"], "Barnes & Noble")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testConditionalUpdate(self):
        """Tests that we can update an entity on C*"""
        from cqlalchemy.connection.functions import when

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            book.publisher = "Barnes & Noble"
            book.set("publisher", "Barnes & Noble", when(publisher="Amazon Kindle"))
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEquals(instance["publisher"], "Barnes & Noble")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testConditionalDelete(self):
        """Tests that we can update an entity on C*"""
        from cqlalchemy.connection.functions import when

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            book.remove("publisher", when(publisher="Amazon Kindle"))
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertIsNone(instance["publisher"])
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testCreateIfNotExists(self):
        """Tests that we can create a unique entity on C*"""
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(
                name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpsert(self):
        """Tests that we can update an existing C* object in place"""
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(
                name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            var = book.id
            found = Book.upsert(
                id=var, name="A Tale of Two Cities", publisher="Amazon Kindle"
            )
            self.assertEqual(book, found)

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testDelete(self):
        """Tests that we can delete an existing C* object in place"""
        from cqlalchemy.connection.cql import Level

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(
                name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            pointer = book.key
            Book.delete(pointer)
        except Exception as e:
            raise e
        finally:
            self.tearDown()


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
            self.assertEquals(instance["publisher"], "Barnes & Noble")
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
            self.assertEquals(instance["publisher"], "Barnes & Noble")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testQueryValue(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            found = Book.objects.contains("A Tale of Two Cities").get()
            self.assertEqual(book, found)
            self.assertEquals(found["publisher"], "Amazon Kindle")
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
            self.assertEquals(found["publisher"], "Amazon Kindle")
        except Exception as e:
            raise e
        finally:
            self.tearDown()


class TestVector(Base):
    def testTable(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.core.models import Table, Vector

        Basket = Table("Basket", Vector)
        self.assertTrue(issubclass(Basket, Vector))

    def testTableOptions(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.time import days
        from cqlalchemy.core.models import Table, Vector

        Basket = Table(
            "Basket", Vector, keyspace="Kindle", version=True, expire=days(30)
        )
        basket = Basket()
        self.assertTrue(issubclass(Basket, Vector))
        self.assertTrue(Basket.__options__.get("version"))
        self.assertTrue(basket.keyspace() == "kindle")
        self.assertTrue(basket.expire == days(30))

    def testCreate(self):
        from cqlalchemy.core.models import Table, Expando

        try:
            Basket = Table("Basket", Expando)
            basket = Basket.create()
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testCreateHybrid(self):
        from cqlalchemy.core.models import Table, Vector

        try:

            class Basket(Vector):
                category = String(index=True)

            basket = Basket.create(category="Vegetables")
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)

            basket = Basket.refresh(basket)
            self.assertTrue(basket.category == "Vegetables")
            self.assertTrue(basket["category"] == "Vegetables")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testCreateIfNotExists(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            basket = Basket.create(data=["Pear", "Strawberry", "Apple"], unique=True)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testRead(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testQuery(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            Basket.create(data=["Pear", "Strawberry", "Apple"])

            basket = Basket.objects.contains(value="Strawberry").get()
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpsert(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])
            Basket.upsert(id=new["id"], data=["Banana", "Strawberry", "Apple"])
            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Banana", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpdate(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])
            new.insert(0, "Banana")
            new.save()

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Banana", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)

        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpdateWithTTL(self):
        import time
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])
            new.insert(0, "Banana", ttl=3)
            new.save()

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Banana", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)

            time.sleep(5)
            basket = Basket.read(new.key)
            self.assertTrue(basket[0] != "Banana")
            self.assertTrue(basket[0] == "Strawberry")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testPrepend(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])
            new.prepend("Banana")
            new.save()

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            self.assertTrue(basket[0] == "Banana")
            for name in ["Banana", "Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testAppend(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])
            new.append("Banana")
            new.save()

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            self.assertTrue(basket[3] == "Banana")
            for name in ["Banana", "Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testExtend(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            new = Basket.create()
            new.extend(["Banana", "Pear", "Strawberry", "Apple"])
            new.save()

            basket = Basket.read(new.key)
            print(basket)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Banana", "Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testStream(self):
        from cqlalchemy.core.models import Table, Vector

        try:
            Basket = Table("Basket", Vector)
            new = Basket.create()
            new.stream()
            new.extend(["Banana", "Pear", "Strawberry", "Apple"])
            new.append("Guava")

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            self.assertTrue(basket[4] == "Guava")
            for name in ["Guava", "Banana", "Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()


class TestBlock(Base):
    def testTable(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.core.models import Table, Block

        Basket = Table("Basket", Block)
        self.assertTrue(issubclass(Basket, Block))

    def testTableOptions(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.time import days
        from cqlalchemy.core.models import Table, Block

        Basket = Table(
            "Basket", Block, keyspace="Kindle", version=True, expire=days(30)
        )
        basket = Basket()
        self.assertTrue(issubclass(Basket, Block))
        self.assertTrue(Basket.__options__.get("version"))
        self.assertTrue(basket.keyspace() == "kindle")
        self.assertTrue(basket.expire == days(30))

    def testCreate(self):
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Basket", Block)
            basket = Basket.create()
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testCreateHybrid(self):
        from cqlalchemy.core.models import Block

        try:

            class Basket(Block):
                category = String(index=True)

            basket = Basket.create(category="Vegetables")
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)

            basket = Basket.refresh(basket)
            self.assertTrue(basket.category == "Vegetables")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testCreateIfNotExists(self):
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Basket", Block)
            basket = Basket.create(data=["Pear", "Strawberry", "Apple"], unique=True)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testRead(self):
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Basket", Block)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testQuery(self):
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Basket", Block)
            Basket.create(data=["Pear", "Strawberry", "Apple"])

            basket = Basket.objects.contains(value="Strawberry").get()
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpsert(self):
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Basket", Block)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])
            Basket.upsert(id=new["id"], data=["Banana", "Strawberry", "Apple"])
            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Banana", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
            self.assertTrue("Pear" not in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpdate(self):
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Basket", Block)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])
            new.add("Banana")
            new.save()
            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Banana", "Strawberry", "Apple", "Pear"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testUpdateWithTTL(self):
        import time
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Basket", Block)
            new = Basket.create(data=["Pear", "Strawberry", "Apple"])
            new.add("Banana", ttl=3)
            new.save()

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            for name in ["Banana", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)

            time.sleep(5)
            basket = Basket.read(new.key)
            self.assertTrue("Banana" not in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testStream(self):
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Basket", Block)
            new = Basket.create()
            new.stream()
            new.extend(["Banana", "Pear", "Strawberry", "Apple"])
            new.add("Guava")

            basket = Basket.read(new.key)
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
            self.assertTrue("Guava" in basket)
            for name in ["Guava", "Banana", "Pear", "Strawberry", "Apple"]:
                self.assertTrue(name in basket)
        except Exception as e:
            raise e
        finally:
            self.tearDown()


class TestCounter(Base):
    def testTable(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.core.commons import Counter64
        from cqlalchemy.core.models import Counter, CounterModel

        Analytics = Counter(
            "Analytics",
            [
                "errors",
            ],
        )
        self.assertTrue(issubclass(Analytics, CounterModel))
        self.assertTrue(isinstance(Analytics.errors, Counter64))

    def testCreate(self):
        from cqlalchemy.core.models import Counter

        try:
            Analytics = Counter(
                "Analytics",
                [
                    "errors",
                ],
            )
            stats = Analytics.create(errors=100)
            self.assertIsNotNone(stats)
            self.assertTrue(stats.saved())
            self.assertIsNotNone(stats.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testRead(self):
        from cqlalchemy.core.models import Counter

        try:
            Analytics = Counter(
                "Analytics",
                [
                    "exceptions",
                ],
            )
            stats = Analytics.create(exceptions=100)

            stats = Analytics.read(stats.id)
            self.assertEquals(stats["exceptions"], 100)
            self.assertIsNotNone(stats)
            self.assertTrue(stats.saved())
            self.assertIsNotNone(stats.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testIncrement(self):
        from cqlalchemy.core.models import Counter

        try:
            Analytics = Counter(
                "Analytics",
                [
                    "exceptions",
                ],
            )
            stats = Analytics.create(exceptions=100)
            stats.increment("exceptions")
            stats.save()

            stats = Analytics.read(stats.id)
            self.assertEquals(stats["exceptions"], 101)
            self.assertIsNotNone(stats)
            self.assertTrue(stats.saved())
            self.assertIsNotNone(stats.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testDecrement(self):
        from cqlalchemy.core.models import Counter

        try:
            Analytics = Counter(
                "Analytics",
                [
                    "exceptions",
                ],
            )
            stats = Analytics.create(exceptions=100)
            stats.decrement("exceptions")
            stats.save()

            stats = Analytics.refresh(stats)
            self.assertEquals(stats["exceptions"], 99)
            self.assertIsNotNone(stats)
            self.assertTrue(stats.saved())
            self.assertIsNotNone(stats.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()
