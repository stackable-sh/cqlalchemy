from .builtins import fields, json

"""
dump:       
Serializes any Entity object into JSON respecting the property.omit setting which is used for excluding 
for sensitive attributes from serialization (for example password hashes).
    
Returns a valid JSON string object. 
"""


def dump(object, format="json", exclude=[]):
    """Serialize a Model into an output format, only JSON supported for now"""
    from cqlalchemy.core.models import Entity, Model, CqlProperty

    if format != "json":
        raise ValueError("Only JSON serialization supported for now")
    if not isinstance(object, Entity):
        raise ValueError("We can only serialize Entity objects.")
    object.validate()
    properties = fields(object, CqlProperty)
    if isinstance(object, Model):
        response = {}
        for name, prop in list(properties.items()):
            if not prop.omit and prop.saveable() and name not in exclude:
                value = prop.serialize(object[name])
                response[name] = value
        return json.dumps(response)


"""
Serialize:       
This function converts a JSON object into its equivalent Entity.
"""


def load(entity, data, format="json", ignore=[]):
    """Deserialize a string data object into an instance of a Model, only JSON supported for now"""
    from cqlalchemy.core.models import Entity, CqlProperty
    from cqlalchemy.core.builtins import fields

    if format != "json":
        raise ValueError("Only JSON serialization supported for now")
    if not issubclass(entity, Entity):
        raise ValueError("We can only deserialize Entity objects")
    if not isinstance(data, str):
        raise ValueError("We can only parse data from strings")

    data = json.loads(data)
    if not isinstance(data, dict):
        raise ValueError("We expected a JSON Dict, not other types of values")

    model = entity()
    properties = fields(entity, CqlProperty)
    for name, prop in list(properties.items()):
        if not prop.omit and prop.saveable() and name not in ignore:
            value = prop.deserialize(data[name])
            setattr(model, name, value)
    return model


def quote(value):
    """Makes a text value CQL safe by escaping it if necessary"""
    if isinstance(value, bytes):
        value = value.encode("utf_8")
        return "'%s'" % value
    elif isinstance(value, str):
        return "'%s'" % escape(str(value), "'", "''")
    else:
        return str(value)


def name(value):
    """Used to un-quote CQL names properly"""
    if isinstance(value, str):
        value = value.encode("utf_8")
    value = escape(value, "'", "")
    return value


def escape(term, char, replacement):
    if not isinstance(term, str):
        raise ValueError("We can only escape strings")
    return term.replace(char, replacement)
