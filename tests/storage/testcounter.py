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

class TestCounter(Base):
    def testTable(self):
        """Tests that we can use the Table shortcut"""
        from cqlalchemy.core.commons import Counter as Counter64
        from cqlalchemy.core.models import Counter, CounterModel

        Analytics = Counter("Analytics",["errors",])
        self.assertTrue(issubclass(Analytics, CounterModel))
        self.assertTrue(isinstance(Analytics.errors, Counter64))

    def testCreate(self):
        from cqlalchemy.core.models import Counter

        try:
            Analytics = Counter("Analytics", ["errors",])
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
            Analytics = Counter("Analytics",["exceptions",])
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
