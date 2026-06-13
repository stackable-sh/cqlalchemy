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
from cqlalchemy.core.serialization import AutoSchema


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            ext = str(uuid.uuid4())[:8]
            cqlalchemy.configure(
                keyspace=f"SerializationTest_{ext}",
                servers=[
                    "localhost",
                ],
                debug=False,
            )
        except Exception:
            pass

    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            clear()
        except Exception as e:
            raise e


class TestAutoSchema(Base):
    def testNormalStyle(self):
        class Person(Model):
            name = String(required=True)

        class PersonSchema(AutoSchema, entity=Person, lazy=False):
            pass

        self.assertTrue(issubclass(PersonSchema, Schema))
        schema = PersonSchema()
        person = Person(name="Iroiso Ikpokonte")
        val = schema.dumps(person)

        struct = json.loads(val)
        self.assertTrue(struct["name"] == person.name)
        self.assertTrue(struct["id"] == str(person.id))

        var = schema.loads(val)
        self.assertTrue(var is not None)
        self.assertTrue(var.name == person.name)
        self.assertTrue(var.id == person.id)
        self.assertTrue(isinstance(var, Person))

    def testPasswordIsOmitted(self):
        salt = bcrypt.gensalt()

        class Person(Model):
            name = String(required=True)
            password = Password(salt=salt, required=True)

        class PersonSchema(AutoSchema, entity=Person, lazy=False):
            pass

        self.assertTrue(issubclass(PersonSchema, Schema))
        schema = PersonSchema()
        person = Person(name="Iroiso Ikpokonte", password="humdinger")
        val = schema.dumps(person)
        self.assertTrue("password" not in val)

    def testIsOmitted(self):
        class Person(Model):
            name = String(required=True)
            password = String(required=True, omit=True)

        class PersonSchema(AutoSchema, entity=Person, lazy=False):
            pass

        self.assertTrue(issubclass(PersonSchema, Schema))
        schema = PersonSchema()
        person = Person(name="Iroiso Ikpokonte", password="humdinger")
        val = schema.dumps(person)
        self.assertTrue("password" not in val)

    def testAutoField(self):
        class UserHandle(String):
            def serialize(self, value):
                """Transforms the value in this converter into something displayable in JSON"""
                return f"@{value}"

            def deserialize(self, value):
                """Transforms a 'potentially unsafe' value from JSON into something suitable for python"""
                return value.strip("@")

        class Person(Model):
            name = String(required=True)
            username = UserHandle(required=True)

        class PersonSchema(AutoSchema, entity=Person, lazy=False):
            pass

        self.assertTrue(issubclass(PersonSchema, Schema))
        schema = PersonSchema()
        person = Person(name="Iroiso Ikpokonte", username="Iroiso")
        val = schema.dump(person)

        print(val)
        self.assertTrue(val["username"] == "@Iroiso")
        self.assertTrue(val["name"] == "Iroiso Ikpokonte")

        found = schema.load(val)
        self.assertTrue(found.name == person.name)
        self.assertTrue(found.username == person.username)

    def testFunctionalStyle(self):
        class Person(Model):
            name = String(required=True)

        PersonSchema = AutoSchema.new(Person, lazy=False)

        self.assertTrue(issubclass(PersonSchema, Schema))
        schema = PersonSchema()
        person = Person(name="Iroiso Ikpokonte")
        val = schema.dumps(person)

        struct = json.loads(val)
        self.assertTrue(struct["name"] == person.name)
        self.assertTrue(struct["id"] == str(person.id))

        var = schema.loads(val)
        self.assertTrue(var is not None)
        self.assertTrue(var.name == person.name)
        self.assertTrue(var.id == person.id)
        self.assertTrue(isinstance(var, Person))

    def testLoad(self):
        class Person(Model):
            name = String(required=True)

        PersonSchema = AutoSchema.new(Person, lazy=False)
        schema = PersonSchema()
        var = str(uuid.uuid4())
        data = {"id": var, "name": "Iroiso Ikpokonte"}
        person = schema.load(data)
        self.assertTrue(isinstance(person, Person))
        self.assertTrue(person.name == "Iroiso Ikpokonte")
        self.assertTrue(str(person.id) == var)

    def testSequence(self):
        class Person(Model):
            name = String(required=True)
            friends = List(String, required=True)

        PersonSchema = AutoSchema.new(Person, lazy=False)
        schema = PersonSchema()
        var = str(uuid.uuid4())
        data = {
            "id": var,
            "name": "Iroiso Ikpokonte",
            "friends": [
                "Charles",
                "Dickens",
            ],
        }
        person = schema.load(data)
        self.assertTrue(isinstance(person, Person))
        self.assertTrue(person.name == "Iroiso Ikpokonte")
        self.assertTrue(str(person.id) == var)
        self.assertTrue(
            person.friends
            == [
                "Charles",
                "Dickens",
            ]
        )

        val = schema.dump(person)
        self.assertTrue(val["id"] == data["id"])
        self.assertTrue(val["name"] == data["name"])
        self.assertTrue(val["friends"] == data["friends"])

    def testTuple(self):
        class Person(Model):
            name = String(required=True)
            friends = Tuple(String, String, required=True)

        PersonSchema = AutoSchema.new(Person, lazy=False)
        schema = PersonSchema()
        var = str(uuid.uuid4())
        data = {
            "id": var,
            "name": "Iroiso Ikpokonte",
            "friends": [
                "Charles",
                "Dickens",
            ],
        }
        person = schema.load(data)
        self.assertTrue(isinstance(person, Person))
        self.assertTrue(person.name == "Iroiso Ikpokonte")
        self.assertTrue(str(person.id) == var)
        self.assertTrue(
            person.friends
            == tuple(
                [
                    "Charles",
                    "Dickens",
                ]
            )
        )
        val = schema.dumps(person)
        print(val)

        val = json.loads(val)
        self.assertTrue(val["id"] == data["id"])
        self.assertTrue(val["name"] == data["name"])
        self.assertTrue(val["friends"] == data["friends"])

    def testDict(self):
        class Person(Model):
            name = String(required=True)
            friends = Map(String, String, required=True)

        PersonSchema = AutoSchema.new(Person, lazy=False)
        schema = PersonSchema()
        var = str(uuid.uuid4())
        data = {
            "id": var,
            "name": "Iroiso Ikpokonte",
            "friends": {"Charles": "Dickens"},
        }
        person = schema.load(data)
        self.assertTrue(isinstance(person, Person))
        self.assertTrue(person.name == "Iroiso Ikpokonte")
        self.assertTrue(str(person.id) == var)
        self.assertTrue(person.friends == {"Charles": "Dickens"})

        val = schema.dump(person)
        self.assertTrue(val["id"] == data["id"])
        self.assertTrue(val["name"] == data["name"])
        self.assertTrue(val["friends"] == data["friends"])

    def testModelEager(self):
        Book = Table("Book", Expando)

        class Person(Model):
            name = String(required=True)
            book = Reference(Book, required=True)

        PersonSchema = AutoSchema.new(Person, lazy=False)
        BookSchema = AutoSchema.new(Book, lazy=False)

        schema = PersonSchema()
        book = Book(name="War and Peace", author="Leo Tolstoy")
        person = Person(name="Iroiso Ikpokonte", book=book)

        val = schema.dump(person)
        self.assertTrue(val["id"] == str(person["id"]))
        self.assertTrue(val["name"] == person["name"])
        self.assertTrue("key" not in val["book"])
        print(val)

    def testModelLazy(self):
        Book = Table("Book", Expando)

        class Person(Model):
            name = String(required=True)
            book = Reference(Book, required=True)

        PersonSchema = AutoSchema.new(Person, lazy=True)
        BookSchema = AutoSchema.new(Book)

        schema = PersonSchema()
        book = Book(name="War and Peace", author="Leo Tolstoy")
        person = Person(name="Iroiso Ikpokonte", book=book)

        val = schema.dump(person)
        self.assertTrue(val["id"] == str(person["id"]))
        self.assertTrue(val["name"] == person["name"])
        self.assertTrue("key" in val["book"])
        print(val)

    def testPickle(self):
        class Person(Model):
            name = String(required=True)
            friends = Pickle(required=True)

        PersonSchema = AutoSchema.new(Person, lazy=False)
        schema = PersonSchema()
        var = str(uuid.uuid4())
        person = Person(
            id=var,
            name="Charles Dickens",
            friends=[
                "Charles",
                "Dickens",
            ],
        )
        self.assertTrue(isinstance(person, Person))
        self.assertTrue(person.name == "Charles Dickens")
        self.assertTrue(str(person.id) == var)
        self.assertTrue(
            person.friends
            == [
                "Charles",
                "Dickens",
            ]
        )

        val = schema.dump(person)
        found = schema.load(val)
        self.assertTrue(found.id == person.id)
        self.assertTrue(found.name == person.name)
        self.assertTrue(found.friends == person.friends)

    def testBlob(self):
        class Person(Model):
            name = String(required=True)
            photo = Blob(required=True)
            friends = Pickle(required=True)

        PersonSchema = AutoSchema.new(Person, lazy=False)
        schema = PersonSchema()
        person = Person(
            name="Iroiso Ikpokonte", photo=b"*" * 100, friends=["Charles", "Dickens "]
        )

        val = schema.dump(person)
        self.assertTrue(val["id"] == str(person["id"]))
        self.assertTrue(val["name"] == person["name"])
        found = schema.load(val)
        self.assertTrue(found.photo == b"*" * 100)
