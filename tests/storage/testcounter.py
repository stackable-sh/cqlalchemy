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
                keyspace="CounterTest",
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
        from cqlalchemy.core.models import Counter, CounterEntity

        Analytics = Counter("Analytics", variables=["errors",])
        self.assertTrue(issubclass(Analytics, CounterEntity))
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
            self.assertEqual(stats["exceptions"], 100)
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
            stats.incr("exceptions")
            stats.save()

            stats = Analytics.read(stats.id)
            self.assertEqual(stats["exceptions"], 101)
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
            stats.decr("exceptions")
            stats.save()

            stats = Analytics.refresh(stats)
            self.assertEqual(stats["exceptions"], 99)
            self.assertIsNotNone(stats)
            self.assertTrue(stats.saved())
            self.assertIsNotNone(stats.key)
        except Exception as e:
            raise e
        finally:
            self.tearDown()
