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

import uuid
from unittest import TestCase, skip
import traceback

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, Expando, Table, Reference
from cqlalchemy.core.commons import String, Email, Set, Map
from cqlalchemy.connection.table import Schema
from cqlalchemy.connection.functions import when
from cqlalchemy.connection import shutdown

Author = Table("Author", Expando, version=True)
Category = Table("Category", Expando, version=True)

class Person(Model, version=True):
    email = Email(required=True)

class Book(Model, version=True):
    name = String(index=True, required=True)
    publisher = String(index=True, required=True)
    author = Reference(Author)
    categories = Set(Category)
    tags = Map(String, Category)


class Base(TestCase):
    """Base class for C* related tests"""
    shutdown: bool = False
    
    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            self.shutdown = False
            part = str(uuid.uuid4())[:8]
            cqlalchemy.configure(
                keyspace=f"Revision_{part.title()}",
                servers=[
                    "localhost",
                ],
                debug=True,
                verbose=True,
            )
            for name in [Category, Author, Person, Book]:
                Schema.create(name)
        except Exception as e:
            traceback.print_exc()

    
    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            if not self.shutdown:
                self.shutdown = True
                Schema.destroy()
                clear()
        except Exception as e:
            raise e
    
class TestHistory(Base):
    
    def testSave(self):
        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEqual(instance, book)

            instance.publisher = "Barnes & Noble"
            instance.name = "Adventures of Huckleberry Finn"
            instance.save()

            instance = Book.refresh(instance)
            changes = list(instance.history.all())

            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")
            self.assertTrue(len(changes) == 2)
            for change in changes:
                change.summary()
        except Exception as e:
            raise e

    def testUndo(self):
        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEqual(instance, book)

            instance.publisher = "Barnes & Noble"
            instance.set(
                name="Adventures of Huckleberry Finn",
                condition=when(name="A Tale of Two Cities"),
            )
            instance.save()

            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == "Amazon Kindle")

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")
        except Exception as e:
            raise e

    def testRestore(self):
        import time

        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEqual(instance, book)

            instance.publisher = "Barnes & Noble"
            instance.set(
                name="Adventures of Huckleberry Finn",
                condition=when(name="A Tale of Two Cities"),
            )
            instance.save()
            change = instance.history.last()

            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == "Amazon Kindle")
            change = instance.history.last()
            journal = change["journal"]
            print(journal)

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")

            instance.history.restore(to=journal)
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == "Amazon Kindle")
        except Exception as e:
            raise e

    def testRevert(self):
        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEqual(instance, book)

            instance.publisher = "Barnes & Noble"
            instance.set(
                name="Adventures of Huckleberry Finn",
                condition=when(name="A Tale of Two Cities"),
            )
            instance.save()

            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")

            change = instance.history.first()
            change.revert()

            found = Book.refresh(instance)
            self.assertTrue(found.name == "A Tale of Two Cities")
            self.assertTrue(found.publisher == "Amazon Kindle")
        except Exception as e:
            raise e

    def testAt(self):
        import datetime

        try:
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEqual(instance, book)

            instance.publisher = "Barnes & Noble"
            instance.set(
                name="Adventures of Huckleberry Finn",
                condition=when(name="A Tale of Two Cities"),
            )
            instance.save()

            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")

            change = instance.history.at(timestamp=datetime.datetime.now())
            self.assertTrue(change is not None)
        except Exception as e:
            raise e

    def testSpan(self):
        import arrow
        import datetime

        try:
            start = arrow.now().shift(days=-1)
            book = Book.create(name="A Tale of Two Cities", publisher="Amazon Kindle")
            instance = Book.read(book.key)
            self.assertEqual(instance, book)

            instance.publisher = "Barnes & Noble"
            instance.set(
                name="Adventures of Huckleberry Finn",
                condition=when(name="A Tale of Two Cities"),
            )
            instance.save()

            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "A Tale of Two Cities")
            self.assertTrue(instance.publisher == "Amazon Kindle")

            instance.history.undo()
            instance = Book.refresh(instance)
            self.assertTrue(instance.name == "Adventures of Huckleberry Finn")
            self.assertTrue(instance.publisher == "Barnes & Noble")
            end = arrow.now().shift(days=+1)

            results = list(instance.history.all())
            print("Results All: ")
            print(results)


            results = list(instance.history.span(start=start, end=end))
            print("Results Span: ")
            print(results)
            self.assertTrue(len(results) == 4)
        except Exception as e:
            raise e
    
    def testUserContext(self):
        from cqlalchemy.connection.cql import Batch

        try:
            guid = None
            account = Person.create(email="steve@apple.com")
            book = None

            with Batch(user=account) as batch:
                book = Book.create(
                    name="A Tale of Two Cities", publisher="Amazon Kindle"
                )
                other = Book.create(name="A Time to Kill", publisher="Barnes and Noble")
                guid = batch.guid

            self.assertTrue(guid is not None)
            self.assertTrue(book is not None)
            change = book.history.first()
            second = other.history.first()

            self.assertTrue(change is not None)
            self.assertTrue(change["journal"] is not None)
            self.assertTrue(change["journal"] == guid)
            self.assertTrue(second["journal"] == change["journal"])
            user = change["user"]
            self.assertTrue(user is not None)
            self.assertTrue(user.email == "steve@apple.com")
            self.assertEqual(change["user"], second["user"])
        except Exception as e:
            raise e
    
    def testBatchObjects(self):
        from cqlalchemy.connection.cql import Batch

        try:
            guid = None
            account = Person.create(email="steve@apple.com")
            book, author = None, None

            with Batch(user=account) as batch:
                author = Author.create(name="Charles Dickens")
                book = Book.create(
                    name="A Tale of Two Cities",
                    publisher="Amazon Kindle",
                    author=author,
                )
                guid = batch.guid

            self.assertTrue(guid is not None)
            self.assertTrue(book is not None)
            change = book.history.first()
            second = author.history.first()

            self.assertTrue(change is not None)
            self.assertTrue(change["journal"] is not None)
            self.assertTrue(change["journal"] == guid)
            self.assertTrue(second["journal"] == change["journal"])

            user = change["user"]
            self.assertTrue(user is not None)
            self.assertTrue(user.email == "steve@apple.com")
            self.assertEqual(change["user"], second["user"])
        except Exception as e:
            raise e
    
    def testNestedObjects(self):
        from cqlalchemy.connection.cql import Batch

        try:
            guid, parts = None, []
            account = Person.create(email="steve@apple.com")
            book, author = None, None

            with Batch(user=account) as batch:
                author = Author.create(name="Charles Dickens")
                tags = ["horror", "fiction", "romance"]
                for var in tags:
                    tag = Category.create(name=var)
                    parts.append(tag)
                book = Book.create(
                    name="A Tale of Two Cities",
                    publisher="Amazon Kindle",
                    author=author,
                    categories=parts,
                )
                guid = batch.guid

            self.assertTrue(guid is not None)
            self.assertTrue(book is not None)
            change = book.history.first()
            second = author.history.first()

            self.assertTrue(change is not None)
            self.assertTrue(change["journal"] is not None)
            self.assertTrue(change["journal"] == guid)
            self.assertTrue(second["journal"] == change["journal"])

            user = change["user"]
            self.assertTrue(user is not None)
            self.assertTrue(user.email == "steve@apple.com")
            self.assertEqual(change["user"], second["user"])

            for tag in parts:
                found = tag.history.first()
                self.assertTrue(found["journal"] == change["journal"])
                self.assertEqual(change["user"], found["user"])
        except Exception as e:
            raise e

    def testRevertNestedSequence(self):
        from cqlalchemy.connection.cql import Batch

        try:
            guid, parts = None, []
            account = Person.create(email="steve@apple.com")
            book, author = None, None

            with Batch(user=account) as batch:
                author = Author.create(name="Charles Dickens", country="USA")
                tags = ["horror", "fiction", "romance"]
                for var in tags:
                    tag = Category.create(name=var, available=False)
                    parts.append(tag)
                book = Book.create(
                    name="A Tale of Two Cities",
                    publisher="Amazon Kindle",
                    author=author,
                    categories=parts,
                )
                guid = batch.guid

            with Batch(user=account) as batch:
                book.publisher = "Barnes & Noble"
                for category in book.categories:
                    category["available"] = True
                    category.save()
                author = book.author
                author["country"] = "England"
                author.save()
                book.save()

            book = Book.refresh(book)
            for tag in book.categories:
                self.assertTrue(tag["available"] == True)
            self.assertTrue(book.author["country"] == "England")
            self.assertTrue(book.publisher == "Barnes & Noble")

            changes = list(book.history.all())
            self.assertTrue(len(changes) == 2)
            latest = book.history.last()
            latest.summary()
            change = book.history.first()
            change.revert()

            book = Book.refresh(book)
            for tag in book.categories:
                self.assertTrue(tag["available"] == False)
            self.assertTrue(book.author["country"] == "USA")
            self.assertTrue(book.publisher == "Amazon Kindle")
        except Exception as e:
            raise e

    def testRevertNestedRelatedMapping(self):
        from cqlalchemy.connection.cql import Batch

        try:
            guid, parts, collection = None, [], {}
            account = Person.create(email="steve@apple.com")
            book, author = None, None

            with Batch(user=account) as batch:
                author = Author.create(name="Charles Dickens", country="USA")
                tags = ["horror", "fiction", "romance"]
                for var in tags:
                    tag = Category.create(name=var, available=False)
                    parts.append(tag)
                    collection[var] = tag

                book = Book.create(
                    name="A Tale of Two Cities",
                    publisher="Amazon Kindle",
                    author=author,
                    categories=parts,
                    tags=collection,
                )
                guid = batch.guid

            with Batch(user=account) as batch:
                book.publisher = "Barnes & Noble"
                for category in book.categories:
                    category["available"] = True
                    category.save()
                author = book.author
                author["country"] = "England"
                author.save()
                book.save()

            book = Book.refresh(book)
            for tag in book.categories:
                self.assertTrue(tag["available"] == True)
            self.assertTrue(book.author["country"] == "England")
            self.assertTrue(book.publisher == "Barnes & Noble")

            changes = list(book.history.all())
            self.assertTrue(len(changes) == 2)
            latest = book.history.last()
            latest.summary()
            change = book.history.first()
            change.revert()

            book = Book.refresh(book)
            for tag in book.categories:
                self.assertTrue(tag["available"] == False)
            for tag, category in book.tags.items():
                self.assertTrue(category["available"] == False)
            self.assertTrue(book.author["country"] == "USA")
            self.assertTrue(book.publisher == "Amazon Kindle")
        except Exception as e:
            raise e

    def testRevertNestedMapping(self):
        from cqlalchemy.connection.cql import Batch

        try:
            guid, collection = None, {}
            account = Person.create(email="steve@apple.com")
            book, author = None, None

            with Batch(user=account) as batch:
                author = Author.create(name="Charles Dickens", country="USA")
                tags = ["horror", "fiction", "romance"]
                for var in tags:
                    tag = Category.create(name=var, available=False)
                    collection[var] = tag

                book = Book.create(
                    name="A Tale of Two Cities",
                    publisher="Amazon Kindle",
                    author=author,
                    tags=collection,
                )
                guid = batch.guid

            with Batch(user=account) as batch:
                book.publisher = "Barnes & Noble"
                for name, category in book.tags.items():
                    category["available"] = True
                    category.save()
                author = book.author
                author["country"] = "England"
                author.save()
                book.save()

            book = Book.refresh(book)
            for tag in book.tags.values():
                self.assertTrue(tag["available"] == True)
            self.assertTrue(book.author["country"] == "England")
            self.assertTrue(book.publisher == "Barnes & Noble")

            changes = list(book.history.all())
            self.assertTrue(len(changes) == 2)
            latest = book.history.last()
            latest.summary()
            change = book.history.first()
            change.revert()

            book = Book.refresh(book)
            for tag in book.tags.values():
                self.assertTrue(tag["available"] == False)
            self.assertTrue(book.author["country"] == "USA")
            self.assertTrue(book.publisher == "Amazon Kindle")
        except Exception as e:
            raise e

    def testRewind(self):
        from cqlalchemy.connection.cql import Batch
        from cqlalchemy.history import History

        try:
            guid, collection = None, {}
            account = Person.create(email="steve@apple.com")
            book, author = None, None

            with Batch(user=account) as batch:
                author = Author.create(name="Charles Dickens", country="USA")
                tags = ["horror", "fiction", "romance"]
                for var in tags:
                    tag = Category.create(name=var, available=False)
                    collection[var] = tag

                book = Book.create(
                    name="A Tale of Two Cities",
                    publisher="Amazon Kindle",
                    author=author,
                    tags=collection,
                )
                guid = batch.guid

            with Batch(user=account) as batch:
                book.publisher = "Barnes & Noble"
                for name, category in book.tags.items():
                    category["available"] = True
                    category.save()
                author = book.author
                author["country"] = "England"
                author.save()
                book.save()

            book = Book.refresh(book)
            for tag in book.tags.values():
                self.assertTrue(tag["available"] == True)
            self.assertTrue(book.author["country"] == "England")
            self.assertTrue(book.publisher == "Barnes & Noble")

            change = book.history.first()
            entities = list(book.tags.values())
            History.rewind(entities=entities, batch=guid)

            book = Book.refresh(book)
            # Verifies that only the tags have changed. The Book Remains Intact
            for tag in book.tags.values():
                self.assertTrue(tag["available"] == False)
            self.assertTrue(book.author["country"] == "England")
            self.assertTrue(book.publisher == "Barnes & Noble")
        except Exception as e:
            raise e
