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

from typing import Type
import warnings

from wtforms import Form as BaseForm
from wtforms.form import FormMeta
from wtforms import validators
from wtforms import (
    StringField,
    IntegerField,
    FloatField,
    BooleanField,
    SelectField,
    DateField,
    DateTimeField,
    TimeField,
    FileField,
    SubmitField,
    HiddenField,
    RadioField,
    TelField,
    TextAreaField,
    URLField,
    EmailField,
    PasswordField,
    DecimalField,
)

from cqlalchemy.options import debug
from cqlalchemy.core.models import Entity, CqlProperty, UUID, Number
from cqlalchemy.core.builtins import fields
from cqlalchemy.core.commons import (
    Phone,
    Password,
    Currency,
    Country,
    Day,
    Float,
    Double,
    Decimal,
    Integer,
    Long,
    Counter,
    Boolean,
    Choice,
    String,
    Email,
    Text,
    IP,
    Pickle,
    Name,
    URL,
    DateTime,
    Time,
    Date,
    Map,
    Set,
    List,
    Tuple,
    Pickle,
)

__all__ = ["Form",]

class New(FormMeta):
    """
    The metaclass for `Form` and any subclasses of `Form`.

    `FormMeta`'s responsibility is to create the `_unbound_fields` list, which
    is a list of `UnboundField` instances sorted by their order of
    instantiation.  The list is created at the first instantiation of the form.
    If any fields are added/removed from the form, the list is cleared to be
    re-generated on the next instantiation.

    Any properties which begin with an underscore or are not `UnboundField`
    instances are ignored by the metaclass.
    """

    def __new__(cls, name, bases, attrs, **keywords):
        entity = keywords.pop("entity", None)
        keys = keywords.pop("keys", False)
        exclude = keywords.pop("exclude", [])
        only = keywords.pop("only", [])

        fields = {}
        fields.update(attrs)
        if entity:
            created = _generate_(entity, keys=keys, exclude=exclude, only=only)
            for name, field in created.items():
                if name not in fields:
                    fields[name] = field
                else:
                    if debug():
                        warnings.warn("Field: %s already exists, skipping it." % name)
        created = super().__new__(cls, name, bases, fields)
        created.__options__ = {
            "entity": entity,
            "keys": keys,
            "exclude": exclude,
            "only": only,
        }
        return created

    def __init__(cls, name, bases, attrs, **kwargs):
        super().__init__(name, bases, attrs)


#  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Form
# You can use this class to automatically create a Form for an entity.
#
# ```python
# from cqlalchemy.core.entity import Model
# from cqlalchemy.core.forms import Form, new
# from cqlalchemy.core.commons import String, Email


# class Address(Model):
#     apartment = String(index=True, required=True)
#     street = String(index=True, required=True)
#     city = String(index=True, required=True)
#     state = String(index=True, required=True)
#     zip = String(index=True, required=True)
#     country = String(index=True, required=True)

# ```
# You can create a form by extend the Form class and setting the entity attribute
# or by using the Form.new() function. You may then proceed to use the form as you would with WTForms.

# ```python

# # Style 1
# class AddressForm(Form, entity=Address, exclude=["apartment",]):
#     pass

# # Style 2
# AddressForm = Form.new(Address, exclude=["apartment",])
# ```
#  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


class Form(BaseForm, metaclass=New):
    """A form that automatically generates fields for an entity"""

    def populate_obj(self, object: Entity, keys: bool = False, exclude: list[str] = []):
        """Populates the object with the form data"""
        raise NotImplementedError(
            "Unsafe: You could overwrite your keys, please use populate() instead"
        )

    def populate(self, object: Entity, keys: bool = False, exclude: list[str] = []):
        """Populates the object with the form data"""
        if isinstance(object, Entity):
            desc = fields(object, CqlProperty)
            for name, field in self._fields.items():
                if name in exclude:
                    continue
                if desc[name].key and not keys:
                    continue
                field.populate_obj(object, name)
        else:
            super().populate_obj(object)

    @classmethod
    def new(
        cls,
        entity: Type[Entity],
        keys: bool = False,
        exclude: list[str] = [],
        only: list[str] = [],
    ):
        """Dynamically creates a new form for an entity"""
        name = "{name}Form".format(name=entity.__name__)
        kind = type(
            name, (Form,), {}, entity=entity, keys=keys, exclude=exclude, only=only
        )
        if name in globals():
            warnings.warn("Form: %s already exists, overwriting it." % name)
        globals()[name] = kind
        return kind


def _generate_(
    entity: Type[Entity],
    keys: bool = False,
    exclude: list[str] = [],
    only: list[str] = [],
):
    """Generates form fields for an entity"""
    if exclude and only:
        raise ValueError("exclude and only cannot be used together")
    properties = fields(entity(), CqlProperty)
    results = dict()
    for name, desc in properties.items():
        if isinstance(desc, (Map, Set, List, Tuple, Pickle)):
            warnings.warn("Field: %s is not supported, skipping it" % desc)
            continue
        elif desc.__class__ in _fields_:
            val, kwargs = [], {}
            if desc.omit:
                continue
            if exclude and name in exclude:
                continue
            if only and name not in only:
                continue
            if desc.key and not keys:
                continue
            if desc.required:
                val.append(validators.InputRequired())
            if desc.choices and not isinstance(desc, Choice):
                val.append(validators.AnyOf(choices=desc.choices))
            if isinstance(desc, Number):
                val.append(validators.NumberRange(min=desc.minimum, max=desc.maximum))
            elif isinstance(desc, IP):
                val.append(validators.IPAddress(ipv4=True, ipv6=True))
            elif isinstance(desc, Choice):
                choices = [(m.name, m.value) for m in desc.enum]
                options = [m.value for m in desc.enum]
                kwargs["choices"] = choices
                val.append(validators.AnyOf(choices=options))
            elif isinstance(desc, String):
                val.append(validators.Length(min=desc.length))
                if desc.pattern:  # type: ignore
                    val.append(validators.Regexp(desc.pattern))
            elif isinstance(desc, Email):
                val.append(validators.Email())
                if desc.pattern:  # type: ignore
                    val.append(validators.Regexp(desc.pattern))
            elif isinstance(desc, URL):
                val.append(validators.URL())
            elif isinstance(desc, UUID):
                val.append(validators.UUID())
            else:
                pass
            Field = _fields_[desc.__class__]
            kwargs["validators"] = val
            instance = Field(**kwargs)
            results[name] = instance
        else:
            if debug():
                warnings.warn("Field: %s is not supported, skipping it" % desc)
            continue
    return results


_fields_ = {
    Phone: TelField,
    Password: PasswordField,
    Currency: StringField,
    Country: StringField,
    Day: IntegerField,
    Float: FloatField,
    Double: FloatField,
    Decimal: DecimalField,
    Integer: IntegerField,
    Long: IntegerField,
    Boolean: BooleanField,
    Choice: SelectField,
    String: StringField,
    Email: EmailField,
    Text: TextAreaField,
    IP: StringField,
    Name: StringField,
    URL: URLField,
    DateTime: DateTimeField,
    Time: TimeField,
    Date: DateField,
    UUID: StringField,
}
