import os
import tempfile
from unittest import TestCase, skip


import cqlalchemy
from cqlalchemy.connection import online
from cqlalchemy.options import clear
from cqlalchemy.connection.table import Schema
from cqlalchemy.revisions.cli import ActionContext
from cqlalchemy.revisions import Project


class Base(TestCase):
    """Base class for C* related tests"""

    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            """
            self.shutdown = False
            cqlalchemy.configure(
                keyspace="cli_test",
                servers=[
                    "localhost",
                ],
                debug=True,
                verbose=True,
            )
            """
            pass 
        except Exception as e:
            pass 

    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            if online():
                Schema.destroy()
                clear()
        except Exception as e:
            raise e


class TestCLI(Base):
    """Integration tests using the cli as the entry point"""
    
    def testInitWithName(self):
        try:
            with tempfile.TemporaryDirectory() as directory:
                action = ActionContext()
                action.init(name="test", dir=directory)
                self.assertTrue(os.path.exists(os.path.join(directory, "test")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "__init__.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "project.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "README")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "versions")))
                self.assertTrue(os.path.exists(os.path.join(directory, "test", "versions", "__init__.py")))
        except Exception as e:
            raise e
    
    def testInitWithoutName(self):
        try:
            with tempfile.TemporaryDirectory() as directory:
                action = ActionContext()
                action.init(dir=directory)
                self.assertTrue(os.path.exists(os.path.join(directory, "revision")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "__init__.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "project.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "README")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "versions")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revision", "versions", "__init__.py")))
        except Exception as e:
            raise e
    
    def testNew(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext()
            project = action.new(dir=directory, message="new basic migration")
            self.assertTrue(project.valid())
            migrations = project.migrations()
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
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("revision_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 
    
    def testSync(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            project = Project(directory)
            self.assertTrue(project.valid())
            action = ActionContext()
            action.sync(dir=directory)
        except Exception as e:
            raise e
    
    