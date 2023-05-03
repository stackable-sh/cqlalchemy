
from unittest import TestCase
from cqlalchemy.core.differ import Differ
from cqlalchemy.core.models import Model, Property
from cqlalchemy.core.commons import Integer, Float, String, Pickle


class TestDiffer(TestCase):
    '''Basic tests for the current differ implementation'''
    def testSanity(self):
        '''Sanity tests for differ'''
        class Simple(Model):
            pi = Float()
            name = String()
            instances = Integer()
            _hidden = None
            
        simple = Simple(pi = 3.142, name = "Hello", instances = 500, _hidden = 1.0)
        simple.differ.commit()
        del simple.name
        self.assertTrue("_hidden" not in simple.differ.added())
        self.assertTrue("name" in simple.differ.deleted())
        simple.instances = 20
        self.assertTrue("instances" in simple.differ.modified())
        simple["stuff"] = ["Some stuff here".split()]
        self.assertTrue("stuff" in simple.differ.added())
        simple.differ.commit()
        simple.name = "Another-name"
        simple["stuff"].append("Some-more")
        self.assertTrue("name" in simple.differ.added())
        self.assertTrue("stuff" in simple.differ.modified())
    
    def testRevert(self):
        '''Tests differ.revert()'''
        import traceback
        class Simple(Model):
            pi = Float()
            name = String()
            instances = Integer()
        simple = Simple(pi = 3.142, name = "Hello", instances = 500)
        simple.differ.commit()
        
        del simple.pi
        del simple.name
        del simple.instances
        
        self.assertTrue("pi" in simple.differ.deleted())
        self.assertTrue("name" in simple.differ.deleted())
        self.assertTrue("instances" in simple.differ.deleted())
        replica = simple.differ.replica
        try:
            simple.differ.revert()
            self.assertEqual(simple.__store__, replica)
            self.assertEqual(simple.pi, 3.142)
            self.assertEqual(simple.name, "Hello")
            self.assertEqual(simple.instances, 500)
            self.assertEqual(simple["pi"], 3.142)
            self.assertEqual(simple["name"], "Hello")
            self.assertEqual(simple["instances"], 500)
        except Exception as e:
            traceback.print_exc(e)
            raise e
        
        
            
    
