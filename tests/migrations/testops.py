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

import os
import tempfile
from unittest import TestCase, skip


import cqlalchemy
from cqlalchemy.connection.cql import execute
from cqlalchemy.revisions.operations import (
    Table, Field, Column, Index, 
    Schema, Keyspace, Drop, Rename, Truncate
)
from cqlalchemy.time import minutes


class Base(TestCase):
    """Base class for C* related tests"""
    created = False 
    
    @classmethod
    def setUpClass(cls):
        """Configure cqlalchemy globally"""
        try:
            if cls.created:
                return 
            cqlalchemy.configure(
                keyspace="operations",
                servers=[
                    "localhost",
                ],
                debug=True,
                verbose=True,
            )
            execute("CREATE KEYSPACE IF NOT EXISTS operations WITH REPLICATION = {'class' : 'NetworkTopologyStrategy', 'replication_factor' : '3'} AND DURABLE_WRITES = True;")
            cls.created = True
        except Exception as e:
            raise e

    @classmethod
    def tearDownClass(cls):
        """Release resources that have been allocated"""
        try:
            execute("DROP KEYSPACE IF EXISTS operations;")
        except Exception as e:
            raise e


class TestOps(Base):
    """Integration tests using the cli as the entry point"""

    def testSchema(self):
        """Tests the Schema Operation"""
        try:
            keyspace = Keyspace(
                name="operations",
                options={
                    "replication": {"SimpleStrategy": 5}
                }
            )
            keyspace.execute()
            self.assertTrue(keyspace.validate())

            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())
            schema = Schema(keyspace="operations")
            schema.execute()
            self.assertTrue(schema.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")
            execute("DROP KEYSPACE IF EXISTS operations;")

    def testKeyspace(self):
        """Tests the Keyspace Operation"""
        try:
            keyspace = Keyspace(
                name="operations",
                options={
                    "replication": {"NetworkTopologyStrategy": {"us-east": 5, "eu-west": 5}}
                }
            )
            keyspace.execute()
            self.assertTrue(keyspace.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP KEYSPACE IF EXISTS operations;")

    def testTable(self):
        """Tests the Table Operation"""
        try:
            keyspace = Keyspace(
                name="operations",
                options={
                    "replication": {"NetworkTopologyStrategy": 3}
                }
            )
            keyspace.execute()
            self.assertTrue(keyspace.validate())
            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")
    
    def testColumn(self):
        """Creates a Basic Table with Indexes, then Adds a Column to it"""
        try:
            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())

            column = Column(
                keyspace="operations", 
                table="User", 
                name="age", 
                type="int", 
                static=True
            )
            column.execute()
            self.assertTrue(column.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")
    
    def testIndex(self):
        """Creates a Basic Table with Indexes, then Adds a Column to it"""
        try:
            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())

            column = Column(
                keyspace="operations", 
                table="User", 
                name="age", 
                type="int"
            )
            column.execute()
            self.assertTrue(column.validate())

            index = Index(keyspace="operations", table="User", column="age")
            index.execute()
            self.assertTrue(index.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")
    
    def testDropKeyspace(self):
        """Tests Drop operation with a keyspace target"""
        try:
            keyspace = Keyspace(
                name="drop_keyspace",
                options={
                    "replication": {"NetworkTopologyStrategy": 5}
                }
            )
            keyspace.execute()
            self.assertTrue(keyspace.validate())

            drop = Drop(target="Keyspace", keyspace="drop_keyspace")
            drop.execute()
            self.assertTrue(drop.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP KEYSPACE IF EXISTS drop_keyspace;")

    def testDropTable(self):
        """Tests Drop operation with a table target"""
        try:
            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())

            drop = Drop(
                target="Table",
                keyspace="operations", 
                table="User", 
            )
            drop.execute()
            self.assertTrue(drop.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")
    
    def testDropColumn(self):
        """Tests Drop operation with a Column target"""
        try:
            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())

            drop = Drop(
                target="Column",
                keyspace="operations", 
                table="User", 
                column="created"
            )
            drop.execute()
            self.assertTrue(drop.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")
    
    def testDropIndex(self):
        """Tests Drop operation with an Index target"""
        try:
            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())

            drop = Drop(
                target="Index",
                keyspace="operations", 
                table="User", 
                index="name"
            )
            drop.execute()
            self.assertTrue(drop.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")
    
    def testRename(self):
        """Tests the Rename operation"""
        try:
            keyspace = Keyspace(
                name="operations",
                options={
                    "replication": {"NetworkTopologyStrategy": 5}
                }
            )
            keyspace.execute()
            self.assertTrue(keyspace.validate())

            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())

            rename = Rename(
                keyspace="operations", 
                table="User", 
                column="id",
                to="guid"
            )
            rename.execute()
            self.assertTrue(rename.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")
    
    def testTruncate(self):
        """Tests the Truncate operation"""
        try:
            keyspace = Keyspace(
                name="operations",
                options={
                    "replication": {"NetworkTopologyStrategy": 5}
                }
            )
            keyspace.execute()
            self.assertTrue(keyspace.validate())

            table = Table(
                keyspace="operations",
                name="User",
                columns=[ 
                    Field(name="id", type="uuid", primary=True),
                    Field(name="username", type="text", key=True),
                    Field(name="created", type="timestamp", order="DESC"),
                    Field(name="name", type="text", index=True),
                    Field(name="surname", type="text", static=True), 
                ],
                expires=minutes(10),
                comment="The basic model for a user account",
            )
            table.execute()
            self.assertTrue(table.validate())

            rename = Truncate(
                keyspace="operations", 
                table="User"
            )
            rename.execute()
            self.assertTrue(rename.validate())
        except Exception as e:
            raise e
        finally:
            execute("DROP TABLE IF EXISTS User;", keyspace="operations")