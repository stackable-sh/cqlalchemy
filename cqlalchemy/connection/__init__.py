"""Provides a facade to the underlying community python driver for Apache Cassandra"""

import logging
from cassandra.cluster import Cluster
from cassandra.protocol import ProtocolVersion
from cassandra.query import ordered_dict_factory
from cassandra.auth import PlainTextAuthProvider
from cqlalchemy.core.builtins import Global
from cassandra.policies import RoundRobinPolicy

__all__ = [
    "connect",
]

world = Global.instance()


class ConnectionError(Exception):
    """Base class for all Connection related exceptions"""

    pass


def connect(configuration):
    """Uses @configuration object to configure and start the internal python driver"""
    global world
    
    if hasattr(world, "cluster") and getattr(world, "cluster") is not None:
        raise RuntimeError("You cannot setup the internal driver more than once.")
    if configuration["bundle"]:
        cloud = {"secure_connect_bundle", configuration["bundle"]}
    else:
        cloud = None
    authentication = PlainTextAuthProvider(
        username=configuration["username"], password=configuration["password"]
    )
    world.cluster = Cluster(
        contact_points=configuration["servers"],
        port=configuration["port"],
        auth_provider=authentication,
        cloud=cloud,
        ssl_context=configuration.get("ssl", None),
        connect_timeout=configuration["timeout"],
        protocol_version=ProtocolVersion.V6,
        allow_beta_protocol_version=True,
        load_balancing_policy=RoundRobinPolicy(),
    )
    world.session = world.cluster.connect()
    world.session.row_factory = ordered_dict_factory
    world.connected = True
    return world


def offline():
    """Returns True if we are currently disconnected from C*"""
    if hasattr(world, "connected"):
        return world.connected == False
    return True


def online():
    """Returns True if we are currently connected to C*"""
    if hasattr(world, "connected"):
        return world.connected
    return False


def shutdown():
    """Releases all resources used internally by the driver"""
    if hasattr(world, "connected") and hasattr(world, "cluster"):
        if world.connected:
            world.cluster.shutdown()
            world.connected = False
            delattr(world, "cluster")
