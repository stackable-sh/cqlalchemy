
from unittest import TestCase
from cqlalchemy.core.commons import *
from cqlalchemy.core.types import phone, blob
from cqlalchemy.core.models import READONLY, BadValueError
from cqlalchemy.core.models import Model, BadValueError
from datetime import date, datetime

class TestCQLProperty(TestCase):
    '''Basic Tests for CQL properties'''
    
    def testSanity(self):
        '''Show that CQL properties cannot begin with an underscore'''
        with self.assertRaises(BadValueError):
            class Person(Model):
                __mobile = String()
            p = Person()
    
        with self.assertRaises(BadValueError):
            class Person(Model):
                Name = String()
            p = Person()
                
class TestPhone(TestCase):
    '''Tests or the Phone descriptor'''
    def setUp(self):
        '''set up a test phone'''
        class Person(object):
            mobile = Phone(required=True)
            
        self.clasz = Person
        self.person = Person()
        self.person.mobile = phone("+2348094486101")

    def testSanity(self):
        '''sanity tests or a phone'''
        with self.assertRaises(BadValueError):
            self.person.mobile = None
        self.person.mobile = phone("+2348094486101")
           
    def testConversionAndDeconversion(self):
        '''Tests conversion and Deconversion'''
        descriptor = Phone()
        expected = repr(self.person.mobile)
        value = descriptor.convert(self.person, self.person.mobile)
        self.assertEqual(expected, value) 
        
        deserialized = eval(value)
        self.assertEqual(self.person.mobile, deserialized)       
        
            
class TestFloat(TestCase):
    """Tests for the Float Descriptor"""
    def setUp(self):
        class Circle(object):
            """Model a simple circle"""
            data = Float(omit=True)
            radius = Integer()
            pi = Float(default=3.142, mode=READONLY)
            
            def area(self):
                """find area of this circle"""
                return self.pi * self.radius * self.radius
        self.circle = Circle()
    
    def testFloatSanity(self):
        """Sanity checks for Float property"""
        self.assertEqual(self.circle.pi ,3.142)
        self.circle.radius = 34
        self.assertEqual(self.circle.area(), (3.142*34*34))
        self.assertRaises(Exception, lambda: setattr(self.circle,'pi',"3.0"))
        
    def testFloatCoercion(self):
        """Checks to make sure that Floats do coercion"""
        self.circle.data = "23.5"
        self.assertEqual(self.circle.data,23.5)
        
    def testFloatValidation(self):
        """Verifies that float values are validated"""
        self.assertRaises(Exception,lambda: setattr(self.circle,'data',"I'm a float"))
        self.circle.data = 5
        self.assertEqual(self.circle.data, 5.0)
        
             
class TestInteger(TestCase):
    """Tests for the Integer Descriptor"""
    def setUp(self):
        class Balls(object):
            number = Integer(choices=list(range(1,5)))
            sold = Integer()
            random = Integer(default=234534,mode=READONLY)
        self.balls = Balls()
        
    def testIntegerSanity(self):
        """Sanity Checks for Integer()"""
        self.balls.number = 3
        self.assertEqual(self.balls.number,3)
        self.assertEqual(self.balls.random,234534)
        self.balls.sold = "5000"
        self.assertEqual(self.balls.sold,5000)
   
    def testChoicesInIntegers(self):
        """Show that choices paramaters are respected in integers"""
        self.assertRaises(Exception,lambda: setattr(self.balls,'number',7))
    
    def testValidationinIntegers(self):
        """Show that validation work if you pass values that cannot be coerced"""
        self.assertRaises(Exception,lambda: setattr(self.balls, "number" ,"I am an Integer"))
    
    def testOtherPropertyAttributes(self):
        """Tries some attributes from its base classes to see"""
        self.assertRaises(Exception, lambda: setattr(self.balls,'random', 50))
        
class TestDate(TestCase):
    """Tests for the Date descriptor"""
    def setUp(self):
        class Test(object):
            date = Date()
            currentDate = Date(autonow = True)
        self.test = Test()
        
    def testDateSanity(self):
        """Is the Date() descriptor sane"""
        someday = date(1990,8,5)
        today = datetime.now().date()
        self.test.date = today
        self.assertEqual(self.test.date,today)
        self.test.currentDate = someday
        self.assertGreaterEqual(self.test.currentDate,someday) #Always returns the current date.
    
    def testDateTypeCheck(self):
        """Type checking for date objects"""
        self.assertRaises(Exception, lambda: setattr(self.test,"date","Hello"))
        self.assertRaises(Exception, lambda: setattr(self.test, "currentDate",datetime.now().time()))
         
class TestTime(TestCase):
    """Tests for the Time() descriptor"""
    def setUp(self):
        class BirthCert(object):
            birthtime = Time()
            currentTime = Time(autonow = True)
        self.test = BirthCert()

    def testTimeSanity(self):
        """Sanity checks for the Time() descriptor"""
        now = datetime.now().time()
        self.test.birthtime = now
        self.assertEqual(self.test.birthtime,now)
        self.assertGreaterEqual(self.test.currentTime,now)
    
    def testTimeTypeCheck(self):
        """Time checking for time objects"""
        self.assertRaises(Exception, lambda: setattr(self.test, "birthtime","Hello"))
        self.assertRaises(Exception, lambda: setattr(self.test, "birthtime",datetime.now().date()))
        
        
class TestDateTime(TestCase):
    """Tests for the DateTime()"""
    def setUp(self):
        class Person(object):
            birthdate = DateTime()
            modified = DateTime(autonow = True)
        self.test = Person()
        
    def testDateTimeSanity(self):
        """Makes sure DateTime() is sane"""
        now = datetime.now()
        self.test.birthdate = now
        self.assertEqual(self.test.birthdate,now)
        before = self.test.modified
        self.assertGreaterEqual(self.test.modified,before)
        """The next snippet shows that with autonow turned on setting a datetime is irrelevant"""
        before = self.test.modified = now
        self.assertGreaterEqual(self.test.modified,before)
    
    def testDateTimeTypeChecking(self):
        """Verifies that DateTime only receive datetimes'"""
        self.assertRaises(Exception,lambda: setattr(self.test,"birthdate","Hello"))
        self.assertRaises(Exception,lambda: setattr(self.test, 'modified', 3434))
            
class TestURL(TestCase):
    """Tests for URL() descriptor"""
    def setUp(self):
        class Person(object):
            website = URL(default="http://harem.tumblr.com")
        self.test = Person()
     
    def testURLSanity(self):
        """Sanity checks for URL; This is hardly a complete test for URLs"""
        'I rely on the urlparse module internally, so this is rock solid'
        self.test.website = "http://iroiso.tumblr.com"
        self.assertEqual(self.test.website,"http://iroiso.tumblr.com")
        self.test.website = "http://twitter.com/iroiso"
        self.assertEqual(self.test.website,"http://twitter.com/iroiso")
        
    def testURLValidation(self):
        """Makes sure the URL descriptors do URL validation"""
        self.assertRaises(Exception,lambda self: setattr(self.test,'website',"Another"))
        self.assertRaises(Exception, lambda self: setattr(self.test,'website',"Bad URL"))
        self.assertRaises(Exception, lambda self: setattr(self.test,'website',234))        
                  
         
class TestBoolean(TestCase):
    """Tests for the Boolean() descriptor"""
    def setUp(self):
        class Person(object):
            isJapanese = Boolean(default=True)
        self.test = Person()
    
    def testSanity(self):
        """Sanity checks for Boolean"""
        self.test.isJapanese = False
        self.assertEqual(self.test.isJapanese,False)
        self.test.isJapanese = True
        self.assertEqual(self.test.isJapanese,True)
        
    def testCoercion(self):
        """Does Boolean do coercion?"""
        self.test.isJapanese = "Hello"
        self.assertEqual(self.test.isJapanese,True)
        self.test.isJapanese = ""
        self.assertEqual(self.test.isJapanese,False)
        self.test.isJapanese = True
        self.assertEqual(self.test.isJapanese,True)

class TestBlob(TestCase):
    """Tests for Blob() data descriptors"""
    def setUp(self):
        class TestObject(object):
            image = Blob(size= 1024*60)
        self.test = TestObject()
    
    def testSizeKeyword(self):
        """Verifies that Blobs Respect the size keyword"""
        with self.assertRaises(Exception):
            self.test.image = open("./misc/blobs/screenshot.png").read() #To Large
    
    def testBlobAcceptsBlobs(self):
        '''Verifies that you can use the `blob` builtin with the Blob descriptor'''
        image = blob("Some stupid content" * 50, mimetype="application/text")
        self.test.image = image
        
    def testBlobRejectsChoices(self):
        """Makes sure that Blob() rejects choices"""
        with self.assertRaises(BadValueError):
            blob = Blob(choices = ["one","two",])
            
    def testBlobCoercesManyThings(self):
        """Shows that Blobs can coerce any thing that can be coerced with str()"""
        from datetime import datetime
        self.test.image = "Hello I'm a fake image"
        self.test.image = 2243434
        now = datetime.now()
        self.test.image = now
        self.assertEqual(str(now), self.test.image)
        
class TestString(TestCase):
    """Tests for String() data descriptor"""
    def setUp(self):
        class TestObject(object):
            name = String(length = 10)
            pattern = String(pattern="test")
            blog = String(default="http://facebook.com/iroiso/notes")
            mail = String(default="iroiso@live.com", mode = READONLY)
        self.test = TestObject()
    
    def testSanity(self):
        '''Sanity tests for String'''
        self.test.name = 0
        self.assertTrue(self.test.name == "0")
        self.assertTrue(getattr(self.test, "name") == "0")
        
        
    def testLength(self):
        """The length property for String should work"""
        self.test.name = "chidori"
        with self.assertRaises(Exception):
            self.test.name = "some text longer than 10 chars"
    
    def testReadOnly(self):
        """Test Readonly properties"""
        with self.assertRaises(AttributeError):
            self.test.mail = "Another mail address"
        
    def testFailureConditions(self):
        """Type checking does it work"""
        self.test.name = 50
        self.test.name = ["iroiso",]
        self.test.pattern = "testicles"
        print(self.test.name)
        with self.assertRaises(BadValueError):
            self.test.pattern = "Iroiso"
