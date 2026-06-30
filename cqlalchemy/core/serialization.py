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

import warnings
import threading
import base64
from typing import Any, Mapping, Dict

from marshmallow import Schema, ValidationError, fields
from marshmallow.schema import SchemaMeta
from marshmallow import post_load as after
from marshmallow import fields as Fields

from cqlalchemy.core.builtins import json
from cqlalchemy.core.builtins import fields as discover
from cqlalchemy.core.commons import *
from cqlalchemy.core.commons import Counter
from cqlalchemy.core.models import (
    Reference,
    UUID,
    CqlProperty,
    Entity,
    Pointer,
    options,
)

__all__ = [
    "AutoSchema",
]


class Registrar(object):
    """Tracks Schema objects for entities"""

    lock = threading.RLock()
    entities: Dict[Entity, Any] = dict()
    default: Dict[Entity, Any] = dict()

    @classmethod
    def put(self, entity, schema):
        with self.lock:
            self.entities[entity] = schema

    @classmethod
    def get(self, entity, default=None):
        with self.lock:
            return self.entities.get(entity, default)


class New(SchemaMeta):
    """Meta class for automatically generating/registering schemas"""

    def __new__(cls, name, bases, attrs, **keywords):
        entity = keywords.get("entity", None)
        lazy = keywords.get("lazy", False)

        fields = {}
        fields.update(attrs)
        if entity:
            created = _generate_(entity, lazy)
            for name, field in created.items():
                if name not in fields:
                    fields[name] = field
        created = super().__new__(cls, name, bases, fields)
        created.__options__ = {"entity": entity, "lazy": lazy}
        Registrar.put(entity, created)
        return created

    def __init__(cls, name, bases, attrs, **keywords):
        super().__init__(name, bases, attrs)


"""
AutoSchema

A marsmallow schema that generates the serialization fields of an Entity automatically, 
while allowing you to optionally override them.

```python
from cqlalchemy import Model, Expando
from cqlalchemy import String, Email, Reference 
from cqlalchemy import AutoSchema

class Account(Expando):
    email = Email(primary=True)
    id = UUID(index=True, required=True)
    password = Password()
    
class Profile(Model):
    username = String(primary=True)
    name = String(required=True, index=True)
    account = Reference(Account, required=True, index=True)

# Create a schema object with auto generated fields

class ProfileSchema(AutoSchema, entity=Profile, lazy=True):
    pass 
    
# Create an automatic schema using the functional style
AccountSchema = AutoSchema.new(Account, lazy=False)

account = Account.create(email="steve@apple.com")
profile = Profile.create(name="Steve Jobs", username="steve", account=account)

schema = AccountSchema()
data = schema.dump(profile)
print(data)

profile = schema.load(data)
print(profile)
print(profile.account)                    # Returns a Pointer object because we're in lazy mode

profile = schema.load(data, lazy=False)   # Fetches the object and all relations from C* using multiple reads.
print(profile.account)                    # Returns the entire account object.
```
"""


class AutoSchema(Schema, metaclass=New):
    """Automatically generates a schema for an entity"""

    @classmethod
    def new(cls, entity: Entity, lazy: bool = False):
        name = "{name}Schema".format(name=entity.__name__)
        fields = _generate_(entity, lazy)
        kind = type(name, (AutoSchema,), fields, entity=entity, lazy=lazy)
        if name in globals():
            warnings.warn("Schema: %s already exists, overwriting it." % name)
        globals()[name] = kind
        return kind

    @after
    def marshal(self, data, **keywords):
        """Creates a new (unpersisted) entity from deserialized data"""
        entity = options(self, "entity")
        instance = entity()
        for name, value in data.items():
            setattr(instance, name, value)
        instance.validate()
        return instance


class AutoField(fields.Field):
    """Delegates Serialization & Deserializtion to the Descriptor"""

    def __init__(self, entity: Entity, property: CqlProperty, lazy=False, **keywords):
        self.entity = entity
        self.lazy = lazy
        self.property = property
        self.required = keywords.get("required", False)
        super().__init__(**keywords)

    def _serialize(self, value: Any, attr: str | None, obj: Any, **kwargs):
        try:
            if not value and self.required:
                raise ValidationError("`AutoField: %s` is not optional" % attr)
            value = self.property.serialize(value)
            return value
        except Exception as e:
            raise ValidationError("Serialization Error: %s" % e)

    def _deserialize(
        self, value: Any, attr: str | None, data: Mapping[str, Any] | None, **kwargs
    ):
        try:
            if not value and self.required:
                raise ValidationError("`AutoField: %s` is not optional" % attr)
            value = self.property.deserialize(value)
            return value
        except Exception as e:
            raise ValidationError("Deserialization Error: %s" % e)


class BlobField(fields.Field):
    """Serializes Blobs as Base64 strings"""

    def __init__(self, **keywords):
        self.required = keywords.get("required", False)
        super().__init__(**keywords)

    def _serialize(self, value: Any, attr: str | None, obj: Any, **kwargs):
        try:
            if not value and self.required:
                raise ValidationError("`AutoField: %s` is not optional" % attr)
            value = base64.b64encode(value)
            return value
        except Exception as e:
            raise ValidationError("Serialization Error: %s" % e)

    def _deserialize(
        self, value: Any, attr: str | None, data: Mapping[str, Any] | None, **kwargs
    ):
        try:
            if not value and self.required:
                raise ValidationError("`AutoField: %s` is not optional" % attr)
            value = base64.b64decode(value)
            return value
        except Exception as e:
            raise ValidationError("Deserialization Error: %s" % e)


class PointerField(Fields.Field):
    def __init__(self, entity: Entity, lazy=False, **keywords):
        self.entity = entity
        self.lazy = lazy
        self.only = keywords.get("only", None)
        self.required = keywords.get("required", False)
        super().__init__(**keywords)

    def _serialize(self, value: Any, attr: str | None, obj: Any, **kwargs):
        try:
            if not value and self.required:
                raise ValidationError(
                    "`PointerField<%s>` is not optional" % self.entity.__name__
                )
            if not isinstance(value, self.entity):
                raise ValueError("Provide an instance of %s" % self.entity.__name__)
            value.validate()
            if self.lazy:
                parts = {"key": value.key.parts}
                return json.dumps(parts)
            else:
                preferred = Registrar.get(self.entity)
                if preferred:
                    value = preferred().dump(value)
                    return value
                else:
                    parts = {"key": value.key.parts}
                    return json.dumps(parts)
        except Exception as e:
            raise ValidationError("Serialization Error: %s" % e)

    def _deserialize(
        self, value: Any, attr: str | None, data: Mapping[str, Any] | None, **kwargs
    ):
        try:
            if not value and self.required:
                raise ValidationError("`AutoField: %s` is not optional" % attr)
            try:
                value = json.loads(value)
                if "key" not in value:
                    raise ValueError("Not a Pointer")
                parts = value["key"]
                pointer = Pointer(self.entity.__name__, **parts)
                if not self.lazy:
                    return pointer.get()
                else:
                    return pointer
            except ValueError:
                preferred = Registrar.get(self.entity)
                if preferred:
                    value = preferred().load(value, only=self.only)
                    return value
                else:
                    raise ValidationError("Deserialization Error: %s")
        except Exception as e:
            raise ValidationError("Deserialization Error: %s" % e)


def _generate_(entity, lazy):
    """Generate Marshmallow descriptors for an entity."""
    descriptors = discover(entity(), CqlProperty)
    results = dict()
    for name, descriptor in descriptors.items():
        if hasattr(descriptor, "omit") and descriptor.omit:
            continue
        instance = None
        if isinstance(descriptor, Map):
            T, V = descriptor.type
            if issubclass(T, Entity):
                T = PointerField(T, required=descriptor.required, lazy=lazy)
            else:
                T = _fields_.get(T, None)
                if T is None:
                    T = AutoField(
                        entity=entity,
                        property=descriptor,
                        required=descriptor.required,
                        lazy=lazy,
                    )
                else:
                    T = T(required=descriptor.required)

            if issubclass(V, Entity):
                V = PointerField(V, required=descriptor.required, lazy=lazy)
            else:
                V = _fields_.get(V, None)
                if V is None:
                    V = AutoField(
                        entity=entity,
                        property=descriptor,
                        required=descriptor.required,
                        lazy=lazy,
                    )
                else:
                    V = V(required=descriptor.required)
            instance = Fields.Dict(keys=T, values=V, required=descriptor.required)
        elif isinstance(descriptor, (List, Set)):
            if issubclass(descriptor.type, Entity):
                T = PointerField(
                    descriptor.type, required=descriptor.required, lazy=lazy
                )
            else:
                T = _fields_.get(descriptor.type, None)
                if T is None:
                    T = AutoField(
                        entity=entity,
                        property=descriptor,
                        required=descriptor.required,
                        lazy=lazy,
                    )
                else:
                    T = T(required=descriptor.required)
            instance = Fields.List(T, required=descriptor.required)
        elif isinstance(descriptor, (Reference)):
            instance = PointerField(
                descriptor.table, required=descriptor.required, lazy=lazy
            )
        elif isinstance(descriptor, Tuple):
            sc = []
            for T in descriptor.type:
                if isinstance(T, Reference):
                    V = PointerField(T.type, required=descriptor.required)
                else:
                    V = _fields_.get(T.__class__, None)
                    if V is None:
                        V = AutoField(
                            entity=entity,
                            property=descriptor,
                            required=descriptor.required,
                            lazy=lazy,
                        )
                    else:
                        V = V(required=descriptor.required)
                sc.append(V)
            instance = Fields.Tuple(tuple_fields=sc, required=descriptor.required)
        else:
            kind = descriptor.__class__
            T = _fields_.get(kind, None)
            if T:
                instance = T(required=descriptor.required)
            else:
                instance = AutoField(
                    entity=entity,
                    property=descriptor,
                    required=descriptor.required,
                    lazy=lazy,
                )
        results[name] = instance
    return results


_fields_ = {
    Phone: Fields.String,
    Password: Fields.String,
    Currency: Fields.String,
    Float: Fields.Float,
    Double: Fields.Float,
    Decimal: Fields.Decimal,
    Integer: Fields.Integer,
    Long: Fields.Integer,
    Counter: Fields.Integer,
    Boolean: Fields.Boolean,
    Choice: Fields.Enum,
    String: Fields.String,
    Email: Fields.Email,
    Text: Fields.String,
    IP: Fields.IP,
    Pickle: Fields.Raw,
    Name: Fields.String,
    Blob: BlobField,
    URL: Fields.Url,
    DateTime: Fields.DateTime,
    Time: Fields.Time,
    Date: Fields.Date,
    UUID: Fields.UUID,
}
