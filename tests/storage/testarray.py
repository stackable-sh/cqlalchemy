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
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, UUID
from cqlalchemy.core.commons import String, Map, List, Set
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            self.shutdown = False
            cqlalchemy.configure(
                keyspace="ArrayTest",
                servers=[
                    "localhost",
                ],
                debug=False,
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


class TestArray(Base):
    def testDefine(self):
        """Tests that we can use the Define shortcut"""
        from cqlalchemy.core.models import Define, Array

        Basket = Define("Basket", Array)
        self.assertTrue(issubclass(Basket, Array))

    def testTableOptions(self):
        """Tests that we can use the Define shortcut"""
        from cqlalchemy.time import days
        from cqlalchemy.core.models import Define, Array

        Basket = Define(
            "Basket", Array, keyspace="Kindle", version=True, expire=days(30)
        )
        basket = Basket()
        self.assertTrue(issubclass(Basket, Array))
        self.assertTrue(Basket.__options__.get("version"))
        self.assertTrue(basket.keyspace() == "kindle")
        self.assertTrue(basket.expire == days(30))

    def testCreate(self):
        from cqlalchemy.core.models import Define, Expando

        try:
            Basket = Define("Basket", Expando)
            basket = Basket.create()
            self.assertIsNotNone(basket)
            self.assertTrue(basket.saved())
            self.assertIsNotNone(basket.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()

    def testCreateHybrid(self):
        from cqlalchemy.core.models import Define, Array

        try:

            class Basket(Array):
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
            new = Basket.create()
            new.extend(["Banana", "Pear", "Strawberry", "Apple"])
            new.save()

            basket = Basket.read(new.key)
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
        from cqlalchemy.core.models import Define, Array

        try:
            Basket = Define("Basket", Array)
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
