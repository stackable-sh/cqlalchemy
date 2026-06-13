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

from unittest import TestCase


class TestConfiguration(TestCase):
    """Basic Tests for Connection to the Cassandra"""

    def testSanity(self):
        """Test basic connection to Apache Cassandra using the Python Driver"""
        import cqlalchemy
        from cqlalchemy.options import settings, debug, keyspace, verbose

        world = cqlalchemy.configure(
            keyspace="OptionsTest",
            servers=[
                "localhost",
            ],
            debug=False,
            verbose=True,
        )
        self.assertIsNotNone(world.cluster)
        self.assertIsNotNone(world.session)
        self.assertTrue(verbose())
        self.assertFalse(debug())
        self.assertTrue(settings())
        self.assertEqual(keyspace(), "optionstest")

        with self.assertRaises(RuntimeError):
            world = cqlalchemy.configure(
                keyspace="OptionsTest",
                servers=[
                    "localhost",
                ],
            )  # You can't configure Cqlalchemy twice
