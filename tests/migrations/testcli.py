
import os
import tempfile
from contextlib import suppress
from unittest import TestCase, skip



import cqlalchemy
import cqlalchemy.options
from cqlalchemy.connection import online
from cqlalchemy.connection.cql import execute
from cqlalchemy.connection.table import Schema
from cqlalchemy.revisions.cli import ActionContext
from cqlalchemy.revisions import Revision, State
from cqlalchemy.revisions.cli.commands import RevisionChecksumException, RevisionAppliedException


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
    
    def testSync(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            action.sync()
        except Exception as e:
            raise e

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
    
    def testStamp(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            action.new(message="new basic migration")
            self.assertTrue(action.project.valid())
            action.migrate()

            migration = action.project.migrations()[0]
            revision = Revision.find(migration.revision)
            self.assertEqual(revision.state, State.APPLIED)

            action.stamp(revision=migration.revision, state=State.FAILED)
            revision = Revision.refresh(revision)
            self.assertEqual(revision.state, State.FAILED)

            action.stamp(revision=migration.revision, state=State.APPLIED)
            revision = Revision.refresh(revision)
            self.assertEqual(revision.state, State.APPLIED)
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 

    def testMultipleMigrations(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            migrations = [
                "new basic migration 1",
                "new basic migration 2",
                "new basic migration 3"
            ]
            for message in migrations:
                action.new(message=message, create=False)
            action.migrate()
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 
    
    def testMultipleMigrationsWithBounds1(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            migrations = [
                "new basic migration 1apple",
                "new basic migration 2ball",
                "new basic migration 3cat"
            ]
            for message in migrations:
                action.new(message=message, create=False)
            action.migrate(start="1apple", stop="2ball")
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 
    
    def testMultipleMigrationsWithBounds2(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            migrations = [
                "new basic migration 1apple",
                "new basic migration 2ball",
                "new basic migration 3cat"
            ]
            for message in migrations:
                action.new(message=message, create=False)
            action.migrate(start="2ball")
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 
    
    def testMultipleMigrationsWithBounds3(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            migrations = [
                "new basic migration 1apple",
                "new basic migration 2ball",
                "new basic migration 3cat"
            ]
            for message in migrations:
                action.new(message=message, create=False)
            action.migrate(stop="3cat")
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 
    
    def testMultipleMigrationsWithBounds4(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            migrations = [
                "new basic migration 1apple",
                "new basic migration 2ball",
                "new basic migration 3cat"
            ]
            for message in migrations:
                action.new(message=message, create=False)
            action.migrate(stop="1apple")
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 
    
    def testMultipleMigrationsWithBounds5(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            self.assertTrue(action.project.valid())
            migrations = [
                "new basic migration 1apple",
                "new basic migration 2ball",
                "new basic migration 3cat"
            ]
            for message in migrations:
                action.new(message=message, create=False)
            action.migrate(start="3cat")
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration)) 

    def testMigrationMakesChecksum(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            action.new(message="new basic migration")
            self.assertTrue(action.project.valid())
            action.migrate()

            migrations = action.project.migrations()
            self.assertTrue(len(migrations) >= 1)
            self.assertEqual(migrations[0].message, "new basic migration")
            self.assertIsNotNone(migrations[0].revision)

            revision = Revision.find(migrations[0].revision)
            self.assertIsNotNone(revision)
            self.assertIsNotNone(revision.checksum)
            self.assertEqual(revision.state, State.APPLIED)
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration))

    def testChangedChecksumTriggersException(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            action.new(message="new basic migration")
            self.assertTrue(action.project.valid())
            action.migrate()

            migrations = action.project.migrations()
            self.assertTrue(len(migrations) >= 1)
            self.assertEqual(migrations[0].message, "new basic migration")
            self.assertIsNotNone(migrations[0].revision)

            migration = action.project.migrations()[0]
            revision = Revision.find(migrations[0].revision)
            self.assertIsNotNone(revision)
            self.assertIsNotNone(revision.checksum)
            self.assertEqual(revision.state, State.APPLIED)

            # Modify the migration file by appending a comment line to it, then attempt to to run the migration again
            with open(migration.path, "a") as f:
                f.write("\n# modified to trigger new migration")

            with suppress(RevisionChecksumException):
                action.migrate(suppress_exceptions=False)
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration))  

    def testChecksumChangeTriggersNewMigration(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            action.new(message="new basic migration")
            self.assertTrue(action.project.valid())
            action.migrate()

            migrations = action.project.migrations()
            self.assertTrue(len(migrations) >= 1)
            self.assertEqual(migrations[0].message, "new basic migration")
            self.assertIsNotNone(migrations[0].revision)

            migration = action.project.migrations()[0]
            revision = Revision.find(migrations[0].revision)
            self.assertIsNotNone(revision)
            self.assertIsNotNone(revision.checksum)
            self.assertEqual(revision.state, State.APPLIED)
            checksum = revision.checksum 

            # Modify the migration file by appending a comment line to it, 
            # then attempt to to run the migration again
            with open(migration.path, "a") as f:
                f.write("\n# modified to trigger new migration")

            action.migrate(confirm=True, suppress_exceptions=True)
            new = Revision.find(migrations[0].revision)
            self.assertNotEqual(checksum, new.checksum)
            self.assertEqual(new.state, State.FAILED)
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration))  
    
    def testRunningSameMigrationTwice(self):
        try:
            directory = os.path.join(os.getcwd(), "tests/migrations/revision")
            action = ActionContext(directory=directory)
            action.new(message="new basic migration")
            self.assertTrue(action.project.valid())
            action.migrate()

            migrations = action.project.migrations()
            self.assertTrue(len(migrations) >= 1)
            self.assertEqual(migrations[0].message, "new basic migration")
            self.assertIsNotNone(migrations[0].revision)

            migration = action.project.migrations()[0]
            revision = Revision.find(migrations[0].revision)
            self.assertIsNotNone(revision)
            self.assertIsNotNone(revision.checksum)
            self.assertEqual(revision.state, State.APPLIED)

            with suppress(RevisionAppliedException):
                action.migrate(confirm=True, suppress_exceptions=False)
        except Exception as e:
            raise e
        finally:
            # clean up the generated migration files
            for migration in os.listdir("tests/migrations/revision/versions/"):    
                if migration.startswith("rev_"):
                    os.remove(os.path.join("tests/migrations/revision/versions/", migration))