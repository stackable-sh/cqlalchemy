
"""
This module is used to configure the global behavior of CqlAlchemy.
It allows you to tell cqlalchemy which machines to connect to, how many connections it should maintain, 
how often idle connections should be recycled, which keyspace to connect to by default and etcetera.

This module is thread safe, because we use threads under the hood to maximize connections to the datastore. 

"""
import os
import copy
import ipaddress
from ssl import SSLContext
from threading import Lock
from schema import Schema, SchemaError, Or

__all__ = ["ConfigurationError", "debug", "settings", "configure",]


class ConfigurationError(Exception):
    '''Thrown to signal a problem with CQLAlchemy settings.'''
    pass
    

__defaults__ = {
    "debug" : True,
    "verbose" : True,
    "timeout" : 30,
    "servers" : ["127.0.0.1",],
    "port" : 9042,
    "username" : "",
    "password" : "",
    "ssl" : None,
    "bundle" : "",
    "keyspace" : "Test",
    "replication" : {
        "NetworkTopologyStrategy" : 3
    }
}
__configuration__ = {}
__lock__ = Lock()

def __validate__(data):
    '''Validates the configuration passed in as @dict'''
    if data:
        def cluster(servers):
            '''Validates that @servers looks like a vaild cassandra cluster'''
            if not servers or not isinstance(servers, list):
                return False
            for server in servers:
                if not server:
                    return False
            return True
        
        def bundle(path):
            """Checks that the bundle exists on disk"""
            if path:
                return os.path.exists(path)
            return True
        
        def cert(context):
            if context is not None:
                return isinstance(context, SSLContext)
            return True
            
        def strategy(o):
            '''Validates the the strategy object looks like a valid cassandra strategy'''
            if not o or not isinstance(o, dict):
                return False
            validation = Or(
                {"NetworkTopologyStrategy" : int},
                {"NetworkTopologyStrategy" : {str : int}},
                {"SimpleStrategy" : int},
            )
            validation = Schema(validation)
            return bool(validation.validate(o))
            
        validator = Schema({
            "debug" : bool,
            "verbose" : bool,
            "timeout" : int,
            "servers" : cluster,
            "port" : int,
            "username" : str,
            "password" : str,
            "bundle" : bundle,
            "ssl" : cert,
            "keyspace" : str,
            "replication" : strategy
        })
        try:
            for name in __defaults__:
                if name not in data:
                    data[name] = __defaults__[name]
            data = validator.validate(data)
            return data
        except SchemaError as e:
            raise ConfigurationError(e) 
    else:
        raise ConfigurationError("Your config dictionary is empty.")
      
def configure(**keywords):
    """Configures CqlAlchemy using keyword arguments"""
    from cqlalchemy.connection import connect
    global __configuration__
    if not keywords:
        raise ConfigurationError("Pass in the approriate keyword arguments")
    with __lock__:
        __configuration__ = __validate__(keywords)
        return connect(__configuration__)
            
def debug():
    '''Is CQLAlchemy in debug mode or not?'''
    if not __configuration__:
        raise ConfigurationError("No configuration object exists.")
    mode = settings().get("debug", False)
    return mode

def verbose():
    """Is cqlalchemy in verbose mode or not"""
    if not __configuration__:
        raise ConfigurationError("No configuration object exists.")
    mode = settings().get("verbose", False)
    return mode
    
def settings():
    """Returns a copy of the global configuration dictionary"""
    if not __configuration__:
        raise ConfigurationError("No configuration object exists.")
    return copy.deepcopy(__configuration__)  

def keyspace():
    '''Returns the default keyspace for this project'''
    keyspace = settings().get("keyspace", None)
    if not keyspace:
        raise ConfigurationError("Please define a keyspace in your configuration")
    return keyspace
