import uuid
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, UUID
from cqlalchemy.core.commons import String, Map, List, Set, Tuple, Integer
from cqlalchemy.connection.table import Schema


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
                editions = Map(String, String, index=Index.Keys)

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

    def testQueryKey(self):
        from cqlalchemy.core.models import Index, Expando

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=Index.Keys)

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

            result = Book\
                .objects\
                .contains(name="editions", key="1st Edition")\
            .get()

            self.assertIsNotNone(result)
            self.assertTrue(result.saved())
            self.assertIsNotNone(result.key)
            self.assertIsNotNone(result.editions)
            self.assertTrue(len(result.editions) == 1)
        except Exception as e:
            raise e

    def testIndexValues(self):
        from cqlalchemy.core.models import Index

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=Index.Values)

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

    def testQueryValues(self):
        from cqlalchemy.core.models import Index
        from cqlalchemy.connection.functions import r 

        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=Index.Values)

            var = str(uuid.uuid4())
            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": var},
            )

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)

            result = Book\
                .objects\
                .where(
                    r("name") == "A Tale of Two Cities",
                    r("editions")["1st Edition"] == var,
                    (r("publisher") == "Amazon Kindle") | (r("publisher") == "Barnes & Noble"),
                )\
                .filter()\
            .get()

            self.assertIsNotNone(result)
            self.assertTrue(result.saved())
            self.assertIsNotNone(result.key)
            self.assertIsNotNone(result.editions)
            self.assertTrue(len(result.editions) == 1)
            self.assertEqual(result.editions["1st Edition"], var)
        except Exception as e:
            raise e    

    def testQueryValueStyle2(self):
        from cqlalchemy.core.models import Index
        from cqlalchemy.connection.functions import r 

        try:
            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Map(String, String, index=Index.Values)

            var = str(uuid.uuid4())
            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions={"1st Edition": var},
            )

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(len(book.editions) == 1)

            result = Book\
                .objects\
                .where(
                    r("name") == "A Tale of Two Cities",
                    r("editions")["1st Edition"] == var,
                    r("publisher") @ ["Amazon Kindle", "Barnes & Noble", "O'Reilly Media"],
                )\
                .filter()\
            .get()

            self.assertIsNotNone(result)
            self.assertTrue(result.saved())
            self.assertIsNotNone(result.key)
            self.assertIsNotNone(result.editions)
            self.assertTrue(len(result.editions) == 1)
            self.assertEqual(result.editions["1st Edition"], var)

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
                editions = Set(String, index=Index.Values)

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
                editions = Set(String, index=Index.Keys)

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
                editions = List(String, index=Index.Values)

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
    

    def testQueryValues(self):
        from cqlalchemy.core.models import Index
        from cqlalchemy.connection.functions import r

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String, index=Index.Values)

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

            result = (
                Book
                    .objects
                    .where(r("editions")[0] == "1st Edition")
                    .filter()
                .get()
            )

            self.assertIsNotNone(result)
            self.assertTrue(result.saved())
            self.assertIsNotNone(result.key)
            self.assertIsNotNone(result.editions)
            self.assertTrue(len(result.editions) == 1)
            self.assertTrue(result.editions[0] == "1st Edition")
        except Exception as e:
            raise e


    def testIndexKeys(self):
        from cqlalchemy.core.models import Index
        from cqlalchemy.connection.table import SchemaError

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = List(String, index=Index.Keys)

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
        """Tests that we can read an entity from C*"""
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
            self.assertEqual(instance["publisher"], "Barnes & Noble")
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

            book.set(
                publisher="Barnes & Noble",
                name="Huckleberry Finn",
                condition=when(
                    publisher="Amazon Kindle"
                )
            )
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEqual(instance["publisher"], "Barnes & Noble")
            self.assertEqual(instance["name"], "Huckleberry Finn")
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testConditionalUpdateStyle2(self):
        """Tests that we can update an entity on C*"""
        from cqlalchemy.connection.functions import when, row

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            book.set(
                publisher="Barnes & Noble", 
                condition=when(
                    row("publisher") == "Amazon Kindle"
                )
            )
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEqual(instance["publisher"], "Barnes & Noble")
        except Exception as e:
            raise e
        finally:
            self.tearDown()
    
    def testConditionalUpdateStyle3(self):
        """Tests that we can update an entity on C*"""
        from cqlalchemy.connection.functions import when, r

        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                price = Integer(index=True, required=True)
                currency = String(index=True, required=True)

            book = Book.create(
                name="A Tale of Two Cities", 
                publisher="Amazon Kindle", 
                price=100,
                currency="USD"
            )

            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            book.set(
                publisher="Barnes & Noble", 
                condition=when(
                    r("publisher") =="Amazon Kindle",
                    r("price")>=80,
                    r("currency") == "NGN" # This condition will fail, so the entire update fails
                )
            )
            book.save()

            instance = Book.read(book.key)
            self.assertEqual(instance, book)
            self.assertEqual(instance["publisher"], "Amazon Kindle")
            self.assertEqual(instance["price"], 100)
            self.assertEqual(instance["currency"], "USD")
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

    def testComplexRead(self):
        """Tests that we can read an entity with complex keys from C*"""
        try:

            class Book(Model):
                id = UUID(primary=True)
                publisher = String(key=True)
                name = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            instance = Book.read({"id": book.id, "publisher": "Amazon Kindle"})
            self.assertEqual(instance, book)

            # Test Read using WHERE queries
            instance = Book.objects.where(id=book.id, publisher="Amazon Kindle").get()
            self.assertEqual(instance, book)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testComplexReadWhere(self):
        """Tests that we can read an entity with complex keys from C*"""
        try:

            class Book(Model):
                id = UUID(primary=True)
                publisher = String(key=True)
                name = String(index=True, required=True)

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            # Test Read using WHERE queries
            instance = Book.objects.where(id=book.id, publisher="Amazon Kindle").get()
            self.assertEqual(instance, book)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testComplexDelete(self):
        """Tests that we can delete an entity with complex keys from C*"""
        from cqlalchemy.connection.cql import Level

        try:

            class Book(Model):
                id = UUID(primary=True)
                publisher = String(key=True)
                name = String(index=True, required=True)

            book = Book.create(
                name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True
            )
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            Book.delete({"id": book.id, "publisher": "Amazon Kindle"})
        except Exception as e:
            raise e
        finally:
            self.tearDown()

class TestTuple(Base):
    
    def testBasic(self):
        try:

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Tuple(String, String)

            instance = Book.create(
                name="A Tale of Two Cities",
                publisher="Amazon Kindle",
                editions=("1st Edition", "2nd Edition"),
            )
            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(book.editions == ("1st Edition", "2nd Edition"))
        except Exception as e:
            raise e

    def testModel(self):
        try:

            class Author(Model):
                name = String(required=True)

            class Book(Model):
                name = String(index=True, required=True)
                publisher = String(index=True, required=True)
                editions = Tuple(String, Author)

            Schema.create(Book)
            Schema.create(Author)

            author = Author.create(name="Lex Luthor")
            packed = ("1st Edition", author)
            instance = Book.create(
                name="A Tale of Two Cities", publisher="Amazon Kindle", editions=packed
            )

            book = Book.read(instance.key)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)
            self.assertIsNotNone(book.editions)
            self.assertTrue(book.editions == packed)
        except Exception as e:
            raise e
