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

from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.differ import commit, changes, Action
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import Integer, Float, String


class TestDiffer(TestCase):
    """Basic tests for the current differ implementation"""

    def setUp(self):
        """Creates a sample class with a Default Property installed on it"""
        cqlalchemy.configure(
            keyspace="DifferTest",
            servers=[
                "localhost",
            ],
            debug=False,
            verbose=True,
        )

    def tearDown(self):
        clear()
        return super().tearDown()

    def testSanity(self):
        """Sanity tests for differ"""

        class Example(Model):
            name = String(key=True)
            count = Integer()
            price = Float()

        example = Example(price=3.142, name="Hello", count=500)
        ops = {operation.name for operation in changes(example)}

        self.assertTrue("name" in ops)
        self.assertTrue("price" in ops)
        self.assertTrue("count" in ops)
        commit(example)

        ops = {operation.name for operation in changes(example)}
        self.assertFalse(ops)
        self.assertFalse("name" in ops)
        self.assertFalse("price" in ops)
        self.assertFalse("count" in ops)

        delattr(example, "price")
        example.name = "World"
        ops = {operation.name for operation in changes(example)}
        self.assertTrue(ops)
        self.assertTrue(len(ops) == 2)
