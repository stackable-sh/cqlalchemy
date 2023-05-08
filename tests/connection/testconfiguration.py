from unittest import TestCase

class TestConfiguration(TestCase):
    '''Basic Tests for Connection to the Cassandra'''
    
    def testSanity(self):
        '''Test basic connection to Apache Cassandra using the Python Driver'''
        from cqlalchemy.options import configure

        world = configure(keyspace="Test", servers=["localhost",])
        self.assertIsNotNone(world.cluster)
        self.assertIsNotNone(world.session)

        with self.assertRaises(RuntimeError):
            world = configure(keyspace="Test", servers=["localhost",]) # You can't configure Cqlalchemy twice
