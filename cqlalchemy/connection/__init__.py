
"""Provides a facade to the underlying community python driver for Apache Cassandra"""

import logging
from cassandra.cluster import Cluster
from cassandra.query import ordered_dict_factory
from cassandra.auth import PlainTextAuthProvider
from cqlalchemy.core.builtins import Global

__all__ = ["connect", ]

shared = Global.instance()


def connect(configuration):
    """Uses @configuration object to configure and start the internal python driver"""
    global shared

    if hasattr(shared, "cluster"):
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
    shared.cluster = cluster

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
    shared.log = logger 

    # Create the shared session object. 
    shared.session = cluster.connect()
    shared.session.row_factory = ordered_dict_factory
    shared.connected = True 
    return shared


def shutdown():
    """Releases all resources used internall by the driver"""
    if shared.connected and hasattr(shared, "cluster"):
        shared.cluster.shutdown()
        shared.connected = False 




