import uuid
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String, Map, List, Set
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    '''Base class for C* related tests'''

    def setUp(self):
        '''Configure home globally'''
        try:
            self.shutdown = False
            cqlalchemy.configure(keyspace="Test", servers=["localhost",], debug=True, verbose=True)
        except Exception as e:
            print(e)
            
    def tearDown(self):
        '''Release resources that have been allocated'''
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
                editions={"1st Edition" : str(uuid.uuid4())}
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
                editions={"1st Edition" : str(uuid.uuid4())}
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
                editions={"1st Edition" : str(uuid.uuid4())}
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
                editions={"1st Edition" : str(uuid.uuid4())}
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
                editions={"1st Edition" : str(uuid.uuid4())}
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
                editions={"1st Edition" : str(uuid.uuid4())}
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
                publisher="Amazon Kindle", editions={"1st Edition",}
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
                publisher="Amazon Kindle", editions={"1st Edition",}
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
                editions={"1st Edition",}
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
                editions={"1st Edition",}
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
                editions={"1st Edition",}
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
                    editions={"1st Edition",}
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
                publisher="Amazon Kindle", editions= ["1st Edition",]
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
                publisher="Amazon Kindle", editions= ["1st Edition",]
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
                publisher="Amazon Kindle", editions=["1st Edition",]
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
                publisher="Amazon Kindle", editions=["1st Edition",]
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
                publisher="Amazon Kindle", editions= ["1st Edition",]
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
                publisher="Amazon Kindle", editions= ["1st Edition",]
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
                publisher="Amazon Kindle", editions= ["1st Edition",]
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
                publisher="Amazon Kindle", editions= ["1st Edition",]
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
                    publisher="Amazon Kindle", editions= ["1st Edition",]
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
                b = Book.create(name="The Adventures of Huckleberry Finn", author="Mark Twain")
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

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True)
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

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True)
            self.assertIsNotNone(book)
            self.assertTrue(book.saved())
            self.assertIsNotNone(book.key)

            var = book.id
            found = Book.upsert(id=var, name="A Tale of Two Cities", publisher="Amazon Kindle")
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

            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True)
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
    """Test the persistence functionality of Model"""

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

    def testCreateIfNotExists(self):
        from cqlalchemy.core.models import Table, Expando
        try:
            Book = Table("Book", Expando)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle", unique=True)
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
            book.put({
                "author" : "Charles Dickens",
                "ttl" : 3
            })
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
            found = Book.upsert(id=var, name="A Tale of Two Cities", publisher="Barnes & Noble")
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

            print(Book.objects)
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

            print(Book.objects)
            found = Book.objects.contains(key="publisher").get()
            self.assertEqual(book, found)
            self.assertEquals(found["publisher"], "Amazon Kindle")
        except Exception as e:
            raise e
        finally:
            self.tearDown()
   

