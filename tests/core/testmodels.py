
from unittest import TestCase
from datetime import datetime, date
from cqlalchemy.core.models import Model, Property, Type, READONLY
from cqlalchemy.core.models import BadValueError, UnIndexable, CqlProperty
        
class TestKeyAndModel(TestCase):
    """Keys and Model where built to work together; they should be tested together"""
    
    def testSanity(self):
        """Makes sure that basic usage for @key works"""
        class Person(Model):
            pass
            
        assert isinstance(Person, type)
        person = Person()
        self.assertTrue(hasattr(person, "id"))
    
    def testModelAcceptsKeywords(self):
        """Tests If accepts keyword arguments and sets them"""
        diction = { "name": "iroiso", "position" : "CEO", "nickname" : "I.I"}
        class Person(Model):
            name = Property()
            position = Property()
            nickname = Property()
        
        person = Person(**diction)
        for name in diction:
            self.assertEqual(getattr(person,name), diction[name])
    
    def testModelDoesNotAcceptUpperCase(self):
        '''Shows that Model does not accept upper case names'''
        with self.assertRaises(BadValueError):
            class Person(Model):
                Name = Property()
            p = Person()

class TestModelDictability(TestCase):
    '''Proves that a Model behaves like a dictionary'''
    def setUp(self):
        '''Common setup code'''
        class Bug(Model):
            name = Property(default="house", required=True)
            reporter = Property(type=str) 
        self.bug = Bug(name = "Gilly")
    
    def testContains(self):
        '''Shows that you can iterate through attributes of a Model like a dictionary'''
        self.bug["house"] = "Blue house"
        self.assertTrue('name' in self.bug)
        self.assertTrue('house' in self.bug)
        
    def testSet(self):
        '''Shows that you can add properties to a Model like a dict, allowing you create wide rows'''
        self.bug["issue_number"] = 1245
        self.assertEqual(self.bug["issue_number"], 1245)
        self.assertTrue("issue_number" in self.bug)
        self.assertTrue("name" in self.bug)
        
    def testRemove(self):
        '''Shows that dict-like subtraction of properties work'''
        self.bug["house"] = "blue"
        self.assertEqual(self.bug["house"], "blue")
        del self.bug["house"]
        del self.bug["name"]
        self.assertFalse("house" in self.bug)
        self.assertFalse("name" in self.bug)
   
    def testKeys(self):
        '''Shows that keys() work properly'''
        class Person(Model):
            name = Property(default = "house", required = True)
            reporter = Property(type = str) 
        person = Person(name="iroiso", reporter="Zainab")
        self.assertTrue("name" in list(person.keys()))
        self.assertTrue("reporter" in list(person.keys()))

    def testValues(self):
        '''Shows that values() work properly'''
        class Values(Model):
            name = Property(default = "house", required = True)
            reporter = Property(type = str) 
        person = Values(name="iroiso", reporter="zainab")
        self.assertTrue("iroiso", "zainab" in list(person.values()))
        
    def testItems(self):
        '''Shows that items() works properly on a Model'''
        item = Model()
        for i in range(50):
            item[str(i)] = i
        comparison = []
        for i in range(50):
            tup = (str(i), i)
            comparison.append(tup)
        bag = list(item.items())
        for tup in comparison:
            self.assertTrue(tup in bag)

    def testIterItems(self):
        '''Test iteritems() to show that it works'''
        item = Model()
        for i in range(50):
            item[str(i)] = i
        comparison = []
        for i in range(50):
            tup = (str(i), i)
            comparison.append(tup)
        for tup in comparison:
            self.assertTrue(tup in iter(item.items()))

    def testIterKeys(self):
        '''Tests that Iteration of over keys work'''
        item = Model()
        comparison = set()
        for i in range(50):
            item[str(i)] = i
            comparison.add(str(i))
        for i in comparison:
            self.assertTrue(i in list(item.keys()))
    
    def testIterValues(self):
        '''Tests that Iteration over values work'''
        item = Model()
        comparison = set()
        for i in range(50):
            item[str(i)] = i
            comparison.add(i)
        for i in comparison:
            self.assertTrue(i in list(item.values()))

    def testLen(self):
        '''Tests for the length of a Model'''
        item = Model()
        for i in range(50):
            item[str(i)] = i
        self.assertTrue(len(item) == 50)
                
"""#.. Tests for home.core.models.Type"""  
class TestType(TestCase):
    """Sanity Checks for Type"""
    def setUp(self):
        """Creates a Type"""
        class Bug(object):
            name = Type(type = str )
            filed = Type(type = date ) 
            
        self.bug = Bug()
           
    def testTypeSanity(self):
        """Makes sure that Type doe type checking"""
        self.assertRaises(Exception, lambda: 
            setattr(self.bug, "filed", "Today"))
        now = datetime.now().date()
        self.bug.filed = now
   
    def testTypeCoercion(self):
        """Does Type do coercion? """
        self.bug.name = 23
        self.assertEqual(self.bug.name, "23")
    
    def testTypeAcceptsPositionalArgs(self):
        """Does type accept positional args"""
        class Blog(object):
            def __init__(self, name, post):
                self.name = name
                self.post = post
                
        class News(object):
            blog = Type(type = Blog)
            
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
            blog = Type(type = Blog)
            
        another = News()
        another.blog = {"name": "iroiso", "post": "a little something"}
        self.assertEqual(another.blog.name, "iroiso")
        self.assertEqual(another.blog.post, "a little something")  
        

"""#.. Tests for home.core.Model.Property"""
class TestProperty(TestCase):
    def setUp(self):
        """Creates a new Bug class everytime"""
        class Bug(object):
            name = Property()
            email = Property(default="iroiso@live.com",mode=READONLY)
            girlfriend = Property(
                default="gwen", 
                choices=["amy","stacy","gwen"],
                required = True
            ) 
        self.Bug = Bug
        self.bug = Bug()
      
    def testReadWriteProperty(self):
        """Makes sure that ReadWrites can be read,written and deleted"""
        setattr(self.bug,"name","Emeka")
        self.assertEqual(self.bug.name , "Emeka")
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
        """Tests this sequence, Delete,Set,Get does it work; Yup I know its crap"""
        setattr(self.bug,"name","First name")
        delattr(self.bug,"name")
        self.assertRaises(AttributeError, lambda: getattr(self.bug,"name"))
        setattr(self.bug,"name","NameAgain")
        self.assertEqual(self.bug.name,"NameAgain")
        delattr(self.bug,"name")
        self.assertRaises(AttributeError, lambda: getattr(self.bug, "name"))
        setattr(self.bug,"name","AnotherNameAgain")
        self.assertEqual(self.bug.name,"AnotherNameAgain")
    
    def testDelete(self):
        """Tests if the del keyword works on READWRITE attributes"""
        self.bug.name = "Emeka"
        del self.bug.name
        self.assertRaises(Exception,lambda:getattr(self.bug,"name"))
         
    def testChoices(self):
        """Tries to set a value that is not a amongst the properties choices"""
        with self.assertRaises(BadValueError):
            self.bug.girlfriend = "steph"
            
    def testRequired(self):
        """Asserts that a required Property cannot be set to None"""
        with self.assertRaises(BadValueError):
            self.bug.girlfriend = None
    
    def testReadOnlyProperty(self):
        """Makes sure that ReadOnlies are immutable """
        with self.assertRaises(ValueError):
            self.readOnly = Property(mode = READONLY)
        with self.assertRaises(AttributeError):
            print("You cannot write to a read only Property")
            setattr(self.bug,"email",100)
        with self.assertRaises(AttributeError):
            print("You cannot delete a read only Property")
            delattr(self.bug,"email")

