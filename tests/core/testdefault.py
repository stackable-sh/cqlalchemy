
from unittest import TestCase
import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.core.models import Default, Model, UUID
from cqlalchemy.core.commons import String, Integer
    
class TestDefault(TestCase):
    '''Does Default work as I expect'''

    def setUp(self):
        '''Creates a sample class with a Default Property installed on it'''
        class Sample(object):
            '''The simplest default class'''
            default = Default()
        self.sample = Sample()
        cqlalchemy.configure(keyspace="Test", servers=["localhost",], debug=True, verbose=True)

    
    def tearDown(self) -> None:
        clear()
        return super().tearDown()

    def testSanity(self):
        '''Tests Expected Behaviour'''
        self.assertRaises(AttributeError, lambda : delattr(self.sample, "default"))
        self.assertRaises(AttributeError, lambda : setattr(self.sample, "default", "Hello"))
        values = self.sample.default
        self.assertTrue(values)
        self.assertTrue(len(values) == 2)
        

    def testOtherDefaultStyle(self):
        '''Tests the other default style'''

        class SecondStyle(Model):
            '''Second pattern of defaults'''
            id = UUID(key=True)
                
            @property
            def default(self):
                '''other style'''
                return String, Integer

        sample = SecondStyle()
        self.assertTrue(len(sample.default) == 2)
        self.assertRaises(AttributeError, lambda : delattr(self.sample, "default"))
        self.assertRaises(AttributeError, lambda : setattr(self.sample, "default", "Hello"))
        values = sample.default
        self.assertTrue(values)
        
        
