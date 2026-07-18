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

import time
from unittest import TestCase, skip

import cqlalchemy
from cqlalchemy.options import keyspace, clear
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String, Text, Map, List, Tuple, Set
from cqlalchemy.core.reflection import Image
from cqlalchemy.connection.table import Schema


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            self.shutdown = False
            cqlalchemy.configure(
                keyspace="reflectiontest",
                servers=[
                    "localhost",
                ],
                debug=False,
            )
        except Exception as e:
            print(e)

    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            if not self.shutdown:
                self.shutdown = True
                Schema.destroy()
                clear()
        except Exception as e:
            raise e


class TestImage(Base):
    """Behavioral Tests for Schema"""

    def testCreateAndImage(self):
        """Tests Image Creation With Default Settings"""
        from cqlalchemy.connection.table import Metadata

        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)

        entity = Book(name="A Tale of Two Cities")
        entity.save()
        self.assertTrue(Book in Schema.entities)
        
        # Wait until the columns and indexes have been created.
        # This is not necessary, striptu sensu, however, I have included it here to service
        # that code path, in case it is ever needed.

        Metadata.block_until(
            keyspace="reflectiontest",
            table="Book",
            index="name"
        )

        Novel = Image(table="Book", base=Model)
        self.assertTrue(hasattr(Novel, "name"))
        self.assertTrue(hasattr(Novel, "id"))

        novel = Novel.create(name="A Tale of Twin Towers")
        self.assertTrue(novel.saved())
        found = Novel.objects.where(name="A Tale of Twin Towers").first()
        self.assertEqual(found, novel)


    def testCreateAndImageWithMap(self):
        """Tests Image Creation With Default Settings"""
        from cqlalchemy.connection.table import Metadata

        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)
            editions = Map(String, String, index=True)

        entity = Book(
            name="A Tale of Two Cities",
            editions={
                "1st Edition" : "John Pepper Clarke",
                "2nd Edition" : "Chukwuemeka Ike"
            }
        )
        entity.save()
        
        Novel = Image(table="Book", base=Model)
        self.assertTrue(hasattr(Novel, "name"))
        self.assertTrue(hasattr(Novel, "id"))
        self.assertTrue(hasattr(Novel, "editions"))

        found = Novel.objects.where(name="A Tale of Two Cities").first()
        self.assertEqual(found, entity)
        self.assertEqual(found.editions, {
                "1st Edition" : "John Pepper Clarke",
                "2nd Edition" : "Chukwuemeka Ike"
        })
    
    def testCreateAndImageWithList(self):
        """Tests Image Creation With Default Settings"""
        from cqlalchemy.connection.table import Metadata

        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)
            editions = List(String, index=True)

        entity = Book(
            name="A Tale of Two Cities",
            editions=["1st Edition", "2nd Edition"]
        )
        entity.save()
        self.assertTrue(Book in Schema.entities)
        
        Novel = Image(table="Book")
        self.assertTrue(hasattr(Novel, "name"))
        self.assertTrue(hasattr(Novel, "id"))
        self.assertTrue(hasattr(Novel, "editions"))

        found = Novel.objects.where(name="A Tale of Two Cities").first()
        self.assertEqual(found, entity)
        self.assertEqual(found.editions, ["1st Edition", "2nd Edition"])

    def testCreateAndImageWithSet(self):
        """Tests Image Creation With Default Settings"""
        from cqlalchemy.connection.table import Metadata

        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)
            editions = Set(String, index=True)

        entity = Book(
            name="A Tale of Two Cities",
            editions={"1st Edition", "2nd Edition"}
        )
        entity.save()
        self.assertTrue(Book in Schema.entities)
        
        Novel = Image(table="Book")
        self.assertTrue(hasattr(Novel, "name"))
        self.assertTrue(hasattr(Novel, "id"))
        self.assertTrue(hasattr(Novel, "editions"))

        found = Novel.objects.where(name="A Tale of Two Cities").first()
        self.assertEqual(found, entity)
        self.assertEqual(found.editions, {"1st Edition", "2nd Edition"})
    
    def testCreateAndImageWithTuple(self):
        """Tests Image Creation With Default Settings"""
        from cqlalchemy.connection.table import Metadata

        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)
            editions = Tuple(String, String, String)

        entity = Book(
            name="A Tale of Two Cities",
            editions=("1st Edition", "2nd Edition", "3rd Edition")
        )
        entity.save()
        self.assertTrue(Book in Schema.entities)
        
        Novel = Image(table="Book")
        self.assertTrue(hasattr(Novel, "name"))
        self.assertTrue(hasattr(Novel, "id"))
        self.assertTrue(hasattr(Novel, "editions"))

        found = Novel.objects.where(name="A Tale of Two Cities").first()
        self.assertEqual(found, entity)
        self.assertEqual(found.editions, ("1st Edition", "2nd Edition", "3rd Edition"))

    def testCreateAndImageWithMetadata(self):
        """Tests Image Creation With Metadata"""
        from cqlalchemy.core.models import options
        from cqlalchemy.connection.table import Metadata

        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)

        entity = Book(name="A Tale of Two Cities")
        entity.save()
        self.assertTrue(Book in Schema.entities)
        
        # Wait until the columns and indexes have been created.
        # This is not necessary, striptu sensu, however, I have included it here to service
        # that code path, in case it is ever needed.

        metadata = Metadata.block_until(
            keyspace="reflectiontest",
            table="Book",
            index="name"
        )

        Novel = Image(
            table="Book", 
            base=Model, 
            metadata=metadata
        )
        self.assertTrue(hasattr(Novel, "name"))
        self.assertTrue(hasattr(Novel, "id"))
        self.assertTrue(options(Novel, "image"))

        novel = Novel.create(name="A Tale of Twin Towers")
        self.assertTrue(novel.saved())
        found = Novel.objects.where(name="A Tale of Twin Towers").first()
        self.assertEqual(found, novel)

    def testCreateAndImageWithOverrides(self):
        """Tests Image Creation with overrides"""
        from cqlalchemy.core.models import options
        from cqlalchemy.connection.table import Metadata

        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)

        entity = Book(name="A Tale of Two Cities")
        entity.save()
        self.assertTrue(Book in Schema.entities)
        
        Novel = Image(
            table="Book", 
            columns={
                "name": Text(index=True, required=True),
            }
        )
        self.assertTrue(hasattr(Novel, "name"))
        self.assertTrue(isinstance(Novel.name, Text))
        self.assertTrue(Novel.name.index)
        self.assertTrue(Novel.name.required)
        self.assertTrue(hasattr(Novel, "id"))
        self.assertTrue(options(Novel, "image"))

        novel = Novel.create(name="A Tale of Twin Towers")
        self.assertTrue(novel.saved())
        found = Novel.objects.where(name="A Tale of Twin Towers").first()
        self.assertEqual(found, novel)
    
    def testCreateAndImageWithExcludes(self):
        """Tests Image Creation With Column Excludes"""
        from cqlalchemy.core.models import options
        from cqlalchemy.connection.table import Metadata

        space = keyspace()
        Schema.create_keyspace(space)
        self.assertTrue(space in Schema.keyspaces)

        class Book(Model):
            name = String(index=True, required=True)

        entity = Book(name="A Tale of Two Cities")
        entity.save()
        self.assertTrue(Book in Schema.entities)
        
        Novel = Image(
            table="Book", 
            exclude=[
                "name",
            ]
        )
        self.assertFalse(hasattr(Novel, "name"))
        self.assertTrue(hasattr(Novel, "id"))
        self.assertTrue(options(Novel, "image"))

        novel = Novel.create()
        self.assertTrue(novel.saved())
        found = Novel.read(entity.id)
        self.assertEqual(found.id, entity.id)
        self.assertEqual(found, entity)
        self.assertFalse(hasattr(found, "name"))