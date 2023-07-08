from unittest import TestCase


class TestConfiguration(TestCase):
    """Basic Tests for Connection to the Cassandra"""

    def testSanity(self):
        """Test basic connection to Apache Cassandra using the Python Driver"""
        import cqlalchemy
        from cqlalchemy.options import settings, debug, keyspace, verbose

        world = cqlalchemy.configure(
            keyspace="Test",
            servers=[
                "localhost",
            ],
            debug=False,
            verbose=True,
        )
        self.assertIsNotNone(world.cluster)
        self.assertIsNotNone(world.session)
        self.assertTrue(verbose())
        self.assertFalse(debug())
        self.assertTrue(settings())
        self.assertEquals(keyspace(), "test")

        with self.assertRaises(RuntimeError):
            world = cqlalchemy.configure(
                keyspace="Test",
                servers=[
                    "localhost",
                ],
            )  # You can't configure Cqlalchemy twice
