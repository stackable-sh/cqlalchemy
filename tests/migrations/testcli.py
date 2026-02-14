import os
import tempfile
from unittest import TestCase


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
    
    def testInit(self):
        try:
            with tempfile.TemporaryDirectory() as directory:
                action = ActionContext()
                action.init(dir=directory)
                self.assertTrue(os.path.exists(os.path.join(directory, "revisions")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revisions", "__init__.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revisions", "project.py")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revisions", "README")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revisions", "versions")))
                self.assertTrue(os.path.exists(os.path.join(directory, "revisions", "versions", "__init__.py")))
        except Exception as e:
            raise e
    
    def testSync(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revisions")
            project = Project(directory)
            self.assertTrue(project.valid())

            action = ActionContext()
            action.sync(dir=directory)
        except Exception as e:
            raise e