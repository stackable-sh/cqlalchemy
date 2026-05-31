import os
import tempfile
from unittest import TestCase, skip


import cqlalchemy
import cqlalchemy.options
from cqlalchemy.connection import online
from cqlalchemy.connection.cql import execute
from cqlalchemy.connection.table import Schema
from cqlalchemy.revisions.cli import ActionContext
from cqlalchemy.revisions import Project


class Base(TestCase):
    """Base class for C* related tests"""

    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            if cqlalchemy.configured():
                Schema.destroy(keyspace="test", tables=["deed", "revision"])
                cqlalchemy.options.clear()
        except Exception as e:
            raise e


class TestCLI(Base):
    """Integration tests using the cli as the entry point"""
    
    @skip
    def testInitWithName(self):
        try:
            with tempfile.TemporaryDirectory() as directory:
                action = ActionContext(directory=directory)
                action.init(name="test")
                self.assertTrue(os.path.exists(os.path.join(directory, "test")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "__init__.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "project.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "README")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "versions")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "versions", "__init__.py")))
        except Exception as e:
            raise e
    
    @skip
    def testInitWithoutName(self):
        try:
            with tempfile.TemporaryDirectory() as directory:
                action = ActionContext(directory=directory)
                action.init()
                self.assertTrue(os.path.exists(os.path.join(directory, "revision")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "__init__.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "project.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "README")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "versions")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "versions", "__init__.py")))
        except Exception as e:
            raise e
    
    @skip
    def testSync(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            action.sync()
        except Exception as e:
            raise e

    @skip
    def testNew(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            self.assertTrue(len(action.project.entities()) > 0)
            action.new(message="new basic migration")
            migrations = action.project.migrations()
            self.assertTrue(len(migrations) >= 1)
            self.assertEqual(migrations[0].message, "new basic migration")
            self.assertIsNotNone(migrations[0].revision)
            self.assertIsNotNone(migrations[0].message)
            self.assertTrue(os.path.exists(migrations[0].path))
            self.assertTrue(len(migrations[0].actions()) >= 1)
            print(migrations[0].actions()[0])
        except Exception as e:
            raise e
        finally:
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 
    
    def testMigrate(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            action.new(message="new basic migration")
            self.assertTrue(action.project.valid())
            action.migrate()
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 