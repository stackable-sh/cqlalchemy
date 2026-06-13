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
import uuid, json

import bcrypt
from marshmallow import Schema

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.commons import String, List, Pickle, Map, Blob, Password, Tuple
from cqlalchemy.core.models import Model, Table, Expando, Reference
from cqlalchemy.core.forms import Form


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            ext = str(uuid.uuid4())[:8]
            cqlalchemy.configure(
                keyspace=f"FormTest_{ext}",
                servers=[
                    "localhost",
                ],
                debug=True,
            )
        except Exception:
            pass

    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            clear()
        except Exception as e:
            raise e


class TestForm(Base):
    """Test Form"""

    def testFormInheritance(self):
        """Create a Form through inheritance"""
        class Person(Model):
            name = String(required=True)
            password = String(required=True, omit=True)

        class PersonForm(Form, entity=Person):
            pass
        
        self.assertTrue(issubclass(PersonForm, Form))
        self.assertTrue(hasattr(PersonForm(), "name"))
        self.assertFalse(hasattr(PersonForm(), "password"))
        self.assertTrue(hasattr(Person(), "id"))
        self.assertFalse(hasattr(PersonForm(), "id"))
    
    def testNewFunction(self):
        """Create a Form through the new function"""
        class User(Model):
            name = String(required=True)
            password = String(required=True, omit=True)

        UserForm = Form.new(User)

        self.assertTrue(issubclass(UserForm, Form))
        self.assertTrue(hasattr(UserForm(), "name"))
        self.assertFalse(hasattr(UserForm(), "password"))
        self.assertTrue(hasattr(User(), "id"))
        self.assertFalse(hasattr(UserForm(), "id"))

    
    
