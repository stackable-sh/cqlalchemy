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

from unittest import TestCase
import uuid


import cqlalchemy
from cqlalchemy.options import clear
from cqlalchemy.connection.table import Schema
from cqlalchemy.core.models import Model, Pointer, UUID
from cqlalchemy.core.commons import String, Integer, Map
from cqlalchemy.connection.cql.partition import (
    extract_partition_fingerprint,
    is_multi_partition,
    detect_multi_partition,
    can_upgrade,
    can_upgrade_queries,
)

class Base(TestCase):
    """Base class for partition detection tests"""
    def setUp(self):
        """Configure cqlalchemy globally"""
        try:
            ext = str(uuid.uuid4())[:8]
            cqlalchemy.configure(
                keyspace=f"PartitionTest_{ext}",
                servers=["localhost"],
                debug=False,
            )
        except Exception:
            pass
    def tearDown(self):
        """Release resources that have been allocated"""
        try:
            clear()
            Schema.clear()
        except Exception as e:
            raise e


class TestPartitionDetection(Base):
    """Tests the partition detection algorithm and fingerprint extraction"""

    def test_fingerprint_extraction_insert(self):
        """Test extracting fingerprint from INSERT queries"""
        class User(Model):
            username = String(primary=True)
            email = String()
        
        # Schema registry should have User now
        q = "INSERT INTO user (username, email) VALUES ('alice', 'alice@example.com');"
        fp = extract_partition_fingerprint(q)
        self.assertIsNotNone(fp)
        self.assertEqual(fp.table, "user")
        self.assertEqual(fp.partition, frozenset([("username", "'alice'")]))

    def test_fingerprint_extraction_update(self):
        """Test extracting fingerprint from UPDATE queries"""
        class Device(Model):
            device_id = UUID(primary=True)
            status = String()
        dev_uuid = str(uuid.uuid4())
        q = f"UPDATE device SET status = 'active' WHERE device_id = {dev_uuid};"
        fp = extract_partition_fingerprint(q)
        self.assertIsNotNone(fp)
        self.assertEqual(fp.table, "device")
        self.assertEqual(fp.partition, frozenset([("device_id", dev_uuid)]))

    def test_fingerprint_extraction_delete(self):
        """Test extracting fingerprint from DELETE queries"""
        class Post(Model):
            post_id = Integer(primary=True)
            title = String()

        q = "DELETE FROM post WHERE post_id = 42;"
        fp = extract_partition_fingerprint(q)
        self.assertIsNotNone(fp)
        self.assertEqual(fp.table, "post")
        self.assertEqual(fp.partition, frozenset([("post_id", "42")]))
        
    def test_fingerprint_extraction_delete_collections(self):
        """Test extracting fingerprint from DELETE queries"""
        class Post(Model):
            post_id = Integer(primary=True)
            title = String()
            editions = Map(String, String)
            
        q = "DELETE editions['UK'] FROM post WHERE post_id = 42;"
        fp = extract_partition_fingerprint(q)
        self.assertIsNotNone(fp)
        self.assertEqual(fp.table, "post")
        self.assertEqual(fp.partition, frozenset([("post_id", "42")]))

    
    def test_fingerprint_extraction_delete_collections_multi(self):
        """Test extracting fingerprint from DELETE queries"""
        class Post(Model):
            post_id = Integer(primary=True)
            title = String()
            editions = Map(String, String)
            
        q = [
            "DELETE editions['2nd Edition'] FROM book WHERE  id='019f2f4d-3935-7613-b353-f148e83a59da';",
            "DELETE editions['3rd Edition'] FROM book WHERE  id='019f2f4d-3935-7613-b353-f148e83a59da';",
            "DELETE editions['UK'] FROM post WHERE post_id = 42;"
        ]
        self.assertTrue(is_multi_partition(q))

        q = [
            "DELETE editions['2nd Edition'] FROM book WHERE  id='019f2f4d-3935-7613-b353-f148e83a59da';",
            "DELETE editions['3rd Edition'] FROM book WHERE  id='019f2f4d-3935-7613-b353-f148e83a59da';",
        ]
        self.assertFalse(is_multi_partition(q))


    def test_composite_partition_keys(self):
        """Test fingerprinting with composite partition keys"""
        class Log(Model):
            app_id = String(primary=True, composite=["env", "service"])
            env = String(key=True)
            service = String(key=True)
            message = String()
        # The partition keys should be app_id, env, service
        q = "INSERT INTO log (app_id, env, service, message) VALUES ('app1', 'prod', 'web', 'hello');"
        fp = extract_partition_fingerprint(q)
        self.assertIsNotNone(fp)
        self.assertEqual(fp.table, "log")
        self.assertEqual(
            fp.partition,
            frozenset([
                ("app_id", "'app1'"),
                ("env", "'prod'"),
                ("service", "'web'")
            ])
        )

    def test_is_multi_partition_queries(self):
        """Test string-based multi-partition detection"""
        class User(Model):
            username = String(primary=True)
        q1 = "INSERT INTO user (username) VALUES ('alice');"
        q2 = "INSERT INTO user (username) VALUES ('bob');"
        q3 = "INSERT INTO user (username) VALUES ('alice');"
        # Different partition values -> multi-partition
        self.assertTrue(is_multi_partition([q1, q2]))
        # Same partition value -> not multi-partition
        self.assertFalse(is_multi_partition([q1, q3]))
        # Single query -> not multi-partition
        self.assertFalse(is_multi_partition([q1]))
        
    def test_detect_multi_partition_objects(self):
        """Test object-based multi-partition detection"""
        class User(Model):
            username = String(primary=True)
        u1 = User(username="alice")
        u2 = User(username="bob")
        u3 = User(username="alice")
        # Different partition values -> multi-partition
        self.assertTrue(detect_multi_partition([u1, u2]))
        # Same partition value -> not multi-partition
        self.assertFalse(detect_multi_partition([u1, u3]))
        # Using Pointer objects
        p1 = Pointer.create(u1)
        p2 = Pointer.create(u2)
        self.assertTrue(detect_multi_partition([p1, p2]))
        self.assertFalse(detect_multi_partition([p1, Pointer.create(u3)]))

    def test_can_escalate(self):
        """Test checking if entities can be escalated to Accord"""
        class AccordModel(Model, accord=True):
            id = UUID(primary=True)
        class LegacyModel(Model, accord=False):
            id = UUID(primary=True)
        a1 = AccordModel(id=uuid.uuid4())
        a2 = AccordModel(id=uuid.uuid4())
        l1 = LegacyModel(id=uuid.uuid4())
        # All support Accord
        self.assertTrue(can_upgrade([a1, a2]))
        # One does not support Accord
        self.assertFalse(can_upgrade([a1, l1]))
        # Using queries
        q_accord = f"INSERT INTO accordmodel (id) VALUES ({uuid.uuid4()});"
        q_legacy = f"INSERT INTO legacymodel (id) VALUES ({uuid.uuid4()});"
        self.assertTrue(can_upgrade_queries([q_accord]))
        self.assertFalse(can_upgrade_queries([q_accord, q_legacy]))