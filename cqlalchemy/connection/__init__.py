
"""Provides a facade to the underlying community python driver for Apache Cassandra"""

import logging
from cassandra.cluster import Cluster
from cassandra.query import ordered_dict_factory
from cassandra.auth import PlainTextAuthProvider
from cqlalchemy.core.builtins import Global

__all__ = ["connect", ]

world = Global.instance()

class ConnectionError(Exception):
    """Base class for all Connection related exceptions"""
    pass 

def connect(configuration):
    """Uses @configuration object to configure and start the internal python driver"""
    global world

    if hasattr(world, "cluster"):
        raise RuntimeError("You cannot setup the internal driver more than once.")
    if configuration["bundle"]:
        cloud = {"secure_connect_bundle", configuration["bundle"]}
    else:
        cloud = None
    authentication = PlainTextAuthProvider(username=configuration["username"], password=configuration["password"])
    cluster = Cluster(
        contact_points=configuration["servers"], 
        port=configuration["port"],
        auth_provider=authentication, 
        cloud=cloud, 
        ssl_context=configuration.get("ssl", None), 
        connect_timeout=configuration["timeout"],
    )
    world.cluster = cluster

    logger = logging.getLogger("cqlalchemy")
    if configuration["verbose"]:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    else:
        logger.setLevel(logging.NOTSET)
        logger.addHandler(logging.NullHandler())
    world.log = logger 

    # Create the global session object. 
    world.session = cluster.connect()
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
    """Releases all resources used internall by the driver"""
    if hasattr(world, "connected") and hasattr(world, "cluster"):
        if world.connected:
            world.cluster.shutdown()
            world.connected = False 
            delattr(world, "cluster")




