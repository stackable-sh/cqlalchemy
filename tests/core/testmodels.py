from unittest import TestCase, skip
from datetime import datetime, date

import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Model, Type, READONLY
from cqlalchemy.core.models import BadValueError, UnIndexable, CqlProperty


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


class TestBasicModel(Base):
    """Keys and Model where built to work together; they should be tested together"""

    def testSanity(self):
        """Makes sure that basic usage for @key works"""

        class Person(Model):
            pass

        assert isinstance(Person, type)
        person = Person()
        self.assertTrue(hasattr(person, "id"))

    def testKeywords(self):
        """Tests If accepts keyword arguments and sets them"""
        from cqlalchemy.core.commons import String, Integer

        class Person(Model):
            name = String(index=True)
            age = Integer()

        data = {"name": "Oliver Twist", "age": 14}
        person = Person(**data)
        for name in data:
            self.assertEqual(getattr(person, name), data[name])

    def testCaseSensitivity(self):
        """Shows that Model does not accept upper case names"""
        with self.assertRaises(BadValueError):

            class Person(Model):
                Name = CqlProperty()

            p = Person()


class TestModelDictability(Base):
    """Proves that a Model behaves like a dictionary"""

    def setUp(self):
        """Common setup code"""
        super(TestModelDictability, self).setUp()

        class Bug(Model):
            name = CqlProperty(default="house", required=True)
            reporter = CqlProperty(type=str)

        self.bug = Bug(name="Gilly")

    def testContains(self):
        """Shows that you can iterate through attributes of a Model like a dictionary"""
        self.bug["reporter"] = "Blue house"
        self.assertTrue("name" in self.bug)
        self.assertTrue("reporter" in self.bug)

    def testRemove(self):
        """Shows that dict-like subtraction of properties work"""
        self.bug["reporter"] = "blue"
        self.assertEqual(self.bug["reporter"], "blue")
        del self.bug["reporter"]
        del self.bug["name"]
        self.assertFalse("reporter" in self.bug)
        self.assertFalse("name" in self.bug)

    def testLen(self):
        """Tests for the length of a Model"""
        self.bug["reporter"] = "Blue"
        self.assertTrue(len(self.bug) == 2)


class TestType(Base):
    """Sanity Checks for Type"""

    def setUp(self):
        """Creates a Type"""
        super(TestType, self).setUp()

        class Bug(object):
            name = Type(type=str)
            filed = Type(type=date)

        self.bug = Bug()

    def testTypeSanity(self):
        """Makes sure that Type doe type checking"""
        self.assertRaises(Exception, lambda: setattr(self.bug, "filed", "Today"))
        now = datetime.now().date()
        self.bug.filed = now

    def testTypeCoercion(self):
        """Does Type do coercion?"""
        self.bug.name = 23
        self.assertEqual(self.bug.name, "23")

    def testTypeAcceptsPositionalArgs(self):
        """Does type accept positional args"""

        class Blog(object):
            def __init__(self, name, post):
                self.name = name
                self.post = post

        class News(object):
            blog = Type(type=Blog)

        news = News()
        news.blog = ["iroiso", "a little something"]
        self.assertEqual(news.blog.name, "iroiso")
        self.assertEqual(news.blog.post, "a little something")

    def testTypeKeywordArgs(self):
        """Does Type accept keyword arguments"""

        class Blog(object):
            def __init__(self, name, post):
                self.name = name
                self.post = post

        class News(object):
            blog = Type(type=Blog)

        another = News()
        another.blog = {"name": "iroiso", "post": "a little something"}
        self.assertEqual(another.blog.name, "iroiso")
        self.assertEqual(another.blog.post, "a little something")


class TestCqlProperty(Base):
    def setUp(self):
        """Creates a new Bug class everytime"""
        super(TestCqlProperty, self).setUp()

        class Bug(object):
            name = CqlProperty()
            email = CqlProperty(default="iroiso@live.com", mode=READONLY)
            girlfriend = CqlProperty(
                default="gwen", choices=["amy", "stacy", "gwen"], required=True
            )

        self.Bug = Bug
        self.bug = Bug()

    def testReadWriteCqlProperty(self):
        """Makes sure that ReadWrites can be read,written and deleted"""
        setattr(self.bug, "name", "Emeka")
        self.assertEqual(self.bug.name, "Emeka")
        delattr(self.bug, "name")
        with self.assertRaises(AttributeError):
            print(self.bug.name)

    def testIndexed(self):
        """Tests if Indexed Properties work"""

        class Bug(object):
            name = CqlProperty(default="A bugs life", indexed=False)
            avatar = UnIndexable()

        self.assertFalse(Bug.name.indexed())
        self.assertFalse(Bug.avatar.indexed())

    def testSetDeleteSetGetWorks(self):
        """Random walks from the execution path"""
        setattr(self.bug, "name", "First name")
        delattr(self.bug, "name")
        self.assertRaises(AttributeError, lambda: getattr(self.bug, "name"))
        setattr(self.bug, "name", "NameAgain")
        self.assertEqual(self.bug.name, "NameAgain")
        delattr(self.bug, "name")
        self.assertRaises(AttributeError, lambda: getattr(self.bug, "name"))
        setattr(self.bug, "name", "AnotherNameAgain")
        self.assertEqual(self.bug.name, "AnotherNameAgain")

    def testDelete(self):
        """Tests if the del keyword works on READWRITE attributes"""
        self.bug.name = "Emeka"
        del self.bug.name
        self.assertRaises(Exception, lambda: getattr(self.bug, "name"))

    def testChoices(self):
        """Tries to set a value that is not a amongst the properties choices"""
        with self.assertRaises(BadValueError):
            self.bug.girlfriend = "steph"

    def testRequired(self):
        """Asserts that a required CqlProperty cannot be set to None"""
        with self.assertRaises(BadValueError):
            self.bug.girlfriend = None

    def testReadOnlyCqlProperty(self):
        """Makes sure that ReadOnlies are immutable"""
        with self.assertRaises(ValueError):
            self.readOnly = CqlProperty(mode=READONLY)
        with self.assertRaises(AttributeError):
            print("You cannot write to a read only CqlProperty")
            setattr(self.bug, "email", 100)
        with self.assertRaises(AttributeError):
            print("You cannot delete a read only CqlProperty")
            delattr(self.bug, "email")
