import sys
import ujson as json
from .builtins import fields


class ComplexObjectException(Exception):
    """Thrown to signify that the serialize function has met a complex object like a list or dict"""
    pass

class EmptyObjectException(Exception):
    """Thrown the signify that the serialize function got a None or another empty value"""
    pass

class InvalidObjectException(Exception):
    """Thrown the signify that the serialize function got a None or another invalid object"""
    pass


"""
dump:       
Serializes an Expando/Model object into JSON, it respects the property.omit setting, 
which can be used to exclude certain properties from serialization.
    
Returns a valid JSON string object. 
"""
def dump(object, format="json"):
    """Serialize a Model into an output format, only JSON supported for now"""
    from cqlalchemy.core.models import Entity, Model, Expando, CqlProperty #We have to do this to avoid recursive imports.
    if format != "json":
        raise ValueError("Only JSON serialization supported for now")
    if not isinstance(object, Entity):
        raise ValueError("We can only serialize Models and Expando Objects")
    
    object.validate()
    properties = fields(object, CqlProperty)
    if isinstance(object, Model):       # SERIALIZATION ROUTINE FOR MODELS
        response = {}
        for name, prop in list(properties.items()):
            if not prop.omit and prop.saveable():
                value = prop.serialize(object[name])
                response[name] = value
        return json.dumps(response)
    elif isinstance(object, Expando):   # SERIALIZATION ROUTINE FOR EXPANDOS
        response = {}
        id = properties.get("id", None)
        if not id:
            raise ValueError("Every Expando must have a declared or implicit ID property")
        k, v = object.default
        for name, value in list(object.items()):
            if name == "id":
                value = id.serialize(object["id"])
                response["id"] = value
                continue 
            value = v.serialize(object[name])
            name = k.serialize(name)
            response[name] = value
        return json.dumps(response)

"""
Serialize:       
This function converts a JSON object into its equivalent CqlAlchemy Model.
"""
def load(kind, data, format="json"):
    """Deserialize a string data object into an instance of a Model, only JSON supported for now"""
    from cqlalchemy.core.models import Entity, CqlProperty, Model, Expando # Avoiding recursive imports
    from cqlalchemy.core.builtins import fields
    
    if format != "json":
        raise ValueError("Only JSON serialization supported for now")
    if not issubclass(kind, Entity):
        raise ValueError("We can only deserialize Models and Expando Objects")
    if not isinstance(data, str):
        raise ValueError("We can only parse data from strings")
    data = json.loads(data, "utf_8")

    if not isinstance(data, dict):
        raise ValueError("CQLAlchemy expects to get a wrapper JSON object, not other types of values")
    
    model = kind()
    properties = fields(kind, CqlProperty)
    if isinstance(model, Model):       # DESERIALIZATION ROUTINE FOR MODELS
        for name, prop in list(properties.items()): # WE RESPECT THE MODEL PROPERTY BOUNDARY HERE.
            if not prop.omit and prop.saveable():
                value = prop.deserialize(data[name])
                setattr(model, name, value)
        return model
    elif isinstance(model, Expando):   # DESERIALIZATION ROUTINE FOR EXPANDOS
        id = properties.get("id", None)
        if not id:
            raise ValueError("Every Expando must have a declared or implicit ID property")
        k, v = kind.default
        for name, value in list(data.items()): # HERE WE JUST EXPAND THE EXPANDO FROM THE PASSED IN DATA
            if name == "id":
                value = id.deserialize(data["id"])
                model["id"] = value
                continue 
            value = v.deserialize(data[name])
            name = k.serialize(name)
            model[name] = value
        return model
   

"""
Size:
Size provide utilities for checking size of objects in bytes
"""    
class Size(object):
    """Provides utility functions to convert to and from bytes, kilobytes, etc."""
    
    @staticmethod
    def inBytes(object):
        """Returns the size of this python object in bytes"""
        return sys.getsizeof(object)

def quote(value):
    '''Makes a text value CQL safe by escaping it if necessary'''
    if isinstance(value, bytes):
        value = value.encode('utf_8')
        return "'%s'" % value
    elif isinstance(value, str):
        return "'%s'" % escape(str(value), "'", "''")
    else:
        return str(value)

def name(value):
    '''Used to un-quote CQL names properly'''
    if isinstance(value, str):
        value = value.encode('utf_8')
    value = escape(value, "'", "")
    return value

def escape(term, char, replacement):
    if not isinstance(term, str): 
        raise ValueError("We can only escape strings")
    return term.replace(char, replacement)
        
    
        
    

