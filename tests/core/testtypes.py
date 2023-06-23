
from cqlalchemy.core.types import phone, blob
from cqlalchemy.core.commons import String
from cqlalchemy.core.differ import changed
from cqlalchemy.core.types import List, Map, Set, ContainerException
from unittest import TestCase, skip


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
        s = List(String)
        s.extend(["Hello", "World", "Welcome", "To", "Australia"])
        self.assertTrue(changed(s))
        s.commit()
        self.assertFalse(changed(s))
    
    def testSetDiffer(self):
        '''Checks that sets can detect changes appropriately'''
        s = Set(String)
        for item in ["Hello", "World", "Welcome", "To", "Australia"]:
            s.add(item)
        self.assertTrue(changed(s))
        s.commit()
        self.assertFalse(changed(s))
    
    def testMapDiffer(self):
        '''Checks that maps can detect changes'''
        m = Map(String, String)
        for i, v in enumerate("Hello World Here"):
            m[i] = v
        self.assertTrue(list(m.changes()))
        m.commit()
        self.assertFalse(list(m.changes()))
         
class TestCollectionLimits(TestCase):
    key, value = "Key" * 65535, "Value" * 65535
    limit = 65535 + 5
    
    def testMapSanity(self):
        '''Show that Map respects Cassandra limits'''
        m = Map(String, String)
        with self.assertRaises(ContainerException): m["hello"] = self.value
        with self.assertRaises(ContainerException): m[self.key] = "value"
        with self.assertRaises(ContainerException): m[self.key] = self.value
        with self.assertRaises(ContainerException):
            for i in range(self.limit):
                m[i] = i
           
    def testListSanity(self):
        '''Show that List respects Cassandra limits'''
        l = List(String)
        with self.assertRaises(ContainerException): l.append(self.value)
        with self.assertRaises(ContainerException):
            for i in range(self.limit):
                l.append(i)
    
    def testSetSanity(self):
        '''Show that Set respects Cassandra limits'''
        l = Set(String)
        with self.assertRaises(ContainerException): l.add(self.value)
        with self.assertRaises(ContainerException):
            for i in range(self.limit):
                l.add(i)
    
        
        
