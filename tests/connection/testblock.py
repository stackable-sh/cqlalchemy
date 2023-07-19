import uuid
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, UUID
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
        except Exception as e:
            raise e
        finally:
            clear()


class TestBlock(Base):
    def testTable(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.core.models import Table, Block

        Basket = Table("Fruits", Block)
        self.assertTrue(issubclass(Basket, Block))

    def testTableOptions(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.time import days
        from cqlalchemy.core.models import Table, Block

        Basket = Table(
            "Fruits", Block, keyspace="Kindle", version=True, expire=days(30)
        )
        basket = Basket()
        self.assertTrue(issubclass(Basket, Block))
        self.assertTrue(Basket.__options__.get("version"))
        self.assertTrue(basket.keyspace() == "kindle")
        self.assertTrue(basket.expire == days(30))

    def testCreate(self):
        from cqlalchemy.core.models import Table, Block

        try:
            Basket = Table("Fruits", Block)
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
            Basket = Table("Fruits", Block)
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
            Basket = Table("Fruits", Block)
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
            Basket = Table("Fruits", Block)
            Basket.create(data=["Pear", "Strawberry", "Apple"])

            basket = Basket.objects.contains(value="Strawberry").get()
            if basket:
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
            Basket = Table("Fruits", Block)
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
            Basket = Table("Fruits", Block)
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
            Basket = Table("Fruits", Block)
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
            Basket = Table("Fruits", Block)
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

