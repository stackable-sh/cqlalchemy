from unittest import TestCase, skip
import uuid, json

from marshmallow import Schema

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.commons import String, List, Pickle
from cqlalchemy.core.models import Model
from cqlalchemy.core.serialization import AutoSchema

class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure home globally"""
        try:
            cqlalchemy.configure(
                keyspace="Test",
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

# TODO : Test Map => Dict
# TODO : Test Model => PointerField
# TODO : Test Blob => BlobField
# TODO : Test AutoField 

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


    def testFunctionalStyle(self):
        class Person(Model):
            name = String(required=True)

        PersonSchema = AutoSchema.create(Person, lazy=False)

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

        PersonSchema = AutoSchema.create(Person, lazy=False)
        schema = PersonSchema()
        var = str(uuid.uuid4())
        data = {
            "id" : var,
            "name" : "Iroiso Ikpokonte"
        }
        person = schema.load(data)
        self.assertTrue(isinstance(person, Person))
        self.assertTrue(person.name == "Iroiso Ikpokonte")
        self.assertTrue(str(person.id) == var)

    def testSequence(self):
        class Person(Model):
            name = String(required=True)
            friends = List(String, required=True)

        PersonSchema = AutoSchema.create(Person, lazy=False)
        schema = PersonSchema()
        var = str(uuid.uuid4())
        data = {
            "id" : var,
            "name" : "Iroiso Ikpokonte",
            "friends" : ["Charles", "Dickens",]
        }
        person = schema.load(data)
        self.assertTrue(isinstance(person, Person))
        self.assertTrue(person.name == "Iroiso Ikpokonte")
        self.assertTrue(str(person.id) == var)
        self.assertTrue(person.friends == ["Charles", "Dickens",])
        
        val = schema.dump(person)
        self.assertTrue(val["id"] == data["id"])
        self.assertTrue(val["name"] == data["name"])
        self.assertTrue(val["friends"] == data["friends"])

    def testPickle(self):
        class Person(Model):
            name = String(required=True)
            friends = Pickle(required=True)

        PersonSchema = AutoSchema.create(Person, lazy=False)
        schema = PersonSchema()
        var = str(uuid.uuid4())
        person = Person(
            id = var,
            name="Charles Dickens",
            friends =["Charles", "Dickens",]
        )
        self.assertTrue(isinstance(person, Person))
        self.assertTrue(person.name == "Charles Dickens")
        self.assertTrue(str(person.id) == var)
        self.assertTrue(person.friends == ["Charles", "Dickens",])
        
        val = schema.dump(person)
        found = schema.load(val)
        self.assertTrue(found.id == person.id)
        self.assertTrue(found.name == person.name)
        self.assertTrue(found.friends == person.friends)


    
