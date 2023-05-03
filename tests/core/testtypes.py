from cqlalchemy.core.types import phone, blob
from cqlalchemy.core.commons import String
from cqlalchemy.core.types import List, Map, Set, CollectionException
from unittest import TestCase

class TestPhone(TestCase):
    '''Unittests for the phone type'''
    
    def testSanity(self):
        '''Makes sure that basic usage is sane'''
        with self.assertRaises(ValueError):
            mobile = phone("(0248) 123-7654")
        mobile = phone("+2348094486101")
    
    def testRepr(self):
        '''Makes sure that phones get a valid python repr'''
        mobile = phone("+2348094486101")
        self.assertEqual(eval(repr(mobile)), mobile)
        
    def testStr(self):
        '''Makes sure that phones are properly stringified'''
        mobile = phone("+2342481237654")
        self.assertEqual("+2342481237654", str(mobile))
        
class TestBlob(TestCase):
    '''Unittests for the blob type'''
    
    def testSanity(self):
        '''Makes sure that basic usage is sane'''
        image = blob(content="Some rubbish text from a file" * 1024, mimetype="image/jpeg", gzipped=True)
        self.assertTrue(image.checksum != None)
        self.assertTrue("gzipped" in image.metadata)
        self.assertTrue(repr(image)) 
        new = eval(repr(image))
        self.assertTrue(isinstance(new, blob))
        self.assertTrue(new == image)

class TestCollectionDifferLogic(TestCase):
    
    def testListDiffer(self):
        '''Checks that lists can detect changes correctly'''
        l = List(String)
        for i in list("Hello World"):
            l.append(i)
        self.assertTrue(l.rewrite())
        l.commit()
        for i in list("Hello Again"):
            l.append(i)
        self.assertFalse(l.rewrite())
        mods = l.modifications()
        pre, app = mods["prepend"], mods["append"]
        self.assertTrue(len(pre) == 0)
        self.assertTrue(len(app) == 11)
        l.commit()
        l.pop(0); l.pop(0); l.pop(len(l)-1)
        self.assertTrue(l.rewrite())
    
    def testSetDiffer(self):
        '''Checks that sets can detect changes appropriately'''
        s = Set(String)
        for i in list("Hello World"):
            s.add(i)
        for i in list("Hello World"):
            self.assertTrue(i in s.added())
        self.assertTrue(len(s.deleted()) == 0)
        print("Testing modification in sets")
        s.commit()
        s.pop(); s.pop(); s.pop()
        self.assertTrue(len(s.added()) == 0)
        self.assertTrue(list(s.deleted()))
        s.commit()
        self.assertTrue(len(s.added()) == 0)
        self.assertTrue(len(s.deleted()) == 0)
    
    def testMapDiffer(self):
        '''Checks that maps can detect changes'''
        m = Map(String, String)
        for i, v in enumerate("Hello World Here"):
            m[i] = v
        self.assertTrue(list(m.added()))
        self.assertFalse(list(m.deleted()))
        self.assertFalse(list(m.modified()))
        m.commit()
        del m[0]; del m[1]; del m[2];
        self.assertTrue(list(m.deleted()))
        m[3] = "Me"; m[5] = "Are"; m[7] = "Us";
        self.assertTrue(list(m.modified()))
                
class TestCollectionLimits(TestCase):
    key = "Key: Something really really long..." * 65535
    value = "Value: Something really really long..." * 65535
    limit = 65535 + 5
    
    def testMapSanity(self):
        '''Show that Map respects Cassandra limits'''
        m = Map(String, String)
        with self.assertRaises(CollectionException): m["hello"] = self.value
        with self.assertRaises(CollectionException): m[self.key] = "value"
        with self.assertRaises(CollectionException): m[self.key] = self.value
        with self.assertRaises(CollectionException):
            for i in range(self.limit):
                m[i] = i
           
    def testListSanity(self):
        '''Show that List respects Cassandra limits'''
        l = List(String)
        with self.assertRaises(CollectionException): l.append(self.value)
        with self.assertRaises(CollectionException):
            for i in range(self.limit):
                l.append(i)
    
    def testSetSanity(self):
        '''Show that Set respects Cassandra limits'''
        l = Set(String)
        with self.assertRaises(CollectionException): l.add(self.value)
        with self.assertRaises(CollectionException):
            for i in range(self.limit):
                l.add(i)
    
        
        
