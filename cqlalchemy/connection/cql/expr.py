
import copy
import textwrap
from typing import Self, Optional, List, Dict, Any, Union

import uuid_utils.compat as uuid
from multidict import MultiDict
from cqlalchemy.core.builtins import assertNonNull, assertType

class Functor(object):
    """An object marker for supported CQL functions"""

    def __init__(self, part: str):
        self.part = part

    def __call__(self, *arguments, **keywords):
        return self.part

    def __str__(self):
        return self.part

class CompositionException(Exception):
    """Exception raised for invalid CQL expressions"""
    pass 

def ttl(name, alias=None) -> Functor:
    """TTL CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Functor(f"TTL({name}) AS {alias}")


def writetime(name, alias=None) -> Functor:
    """WRITETIME CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Functor(f"WRITETIME({name}) AS {alias}")


def avg(name, alias=None) -> Functor:
    """AVG CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Functor(f"AVG({name}) AS {alias}")


def sum(name, alias=None) -> Functor:
    """SUM CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Functor(f"SUM({name}) AS {alias}")


def max(name, alias=None) -> Functor:
    """MAX CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Functor(f"MAX({name}) AS {alias}")


def min(name, alias=None) -> Functor:
    """MIN CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Functor(f"MIN({name}) AS {alias}")


def count(name, alias=None) -> Functor:
    """COUNT CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Functor(f"COUNT({name}) AS {alias}")


class Predicate(object):
    """An expression Composer for rich, idiomatic cql queries in python"""
    entity: "Entity"

    def __init__(self, *arguments, **keywords):
        self.arguments = arguments
        self.keywords = MultiDict(**keywords)
        self.entity = None

    def _build_keywords_(self, output:str, started:bool):
        """Generate CQL from keyword arguments"""
        for name, value in self.keywords.items():
            property = self.entity.__fields__.get(name, None)
            if not property:
                raise ValueError("There is no property: %s in the Entity" % name)

            if isinstance(value, Operator):
                if value.right is None:
                    raise ValueError(
                        "Your Operator must have its RHS set to be valid"
                    )
                value.left = name
                value.entity = self.entity
                value = str(value)
            else:
                operator = EQ(right=value)
                operator.left = name
                operator.entity = self.entity
                value = str(operator)

            if not started:
                output = f" IF {value}"
                started = True
            else:
                output += f" AND {value}"
        return output
    
    def _build_arguments_(self, output:str, started:bool):
        """Generate CQL from positional arguments"""
        for value in self.arguments:
            if not isinstance(value, Operator):
                raise ValueError("All arguments must be of type Operator")
            if value.right is None:
                raise ValueError(
                    "Your Operator must have its RHS set to be valid"
                )
            if value.left is None:
                raise ValueError(
                    "Your Operator must have its LHS set to be valid"
                )
            value.entity = self.entity
            value = str(value)
            if not started:
                output = f" IF {value}"
                started = True
            else:
                output += f" AND {value}"
        return output, started

    def convert(self):
        """Implement the conversion routine for Predicates"""
        if not hasattr(self, "entity"):
            raise ValueError("You need to set Entity for this Predicate to use it")
        output, started = "",False 
        output, started = self._build_arguments_(output, started)
        output = self._build_keywords_(output, started)
        return output

    def __str__(self):
        return self.convert()

class Where(object):
    """Converts from python arguments/keywords to a CQL where statement"""
    entity: "Entity"
    keys_only: bool = False

    def __init__(self, entity:"Entity"):
        self.entity = entity
        self.keywords = MultiDict()
        self.keys_only = False

    def add(self, *arguments, **keywords):
        results = self.parse(*arguments, **keywords)
        for name, value in results.items():
            self.keywords[name] = value 
    
    def parse(self, *arguments, **keywords):
        """Parse WHERE query from python arguments"""
        from cqlalchemy.core.builtins import fields
        from cqlalchemy.core.models import CqlProperty
        from cqlalchemy.connection.cql.expr import Operator, EQ, NULL

        properties = fields(self.entity, CqlProperty)
        disallowed = (NULL,)
        results = MultiDict()

        def validate(name):
            property = properties.get(name, None)
            if not property:
                raise CqlQueryException("Property: %s not found on: %s" % (name, self.entity))
            if self.keys_only and not property.key:
                raise CqlQueryException("This WHERE clause only supports keys: %s" % (name))
            allowed =  property.key or property.indexed() or property.static
            if not allowed:
                raise CqlQueryException("Only use WHERE on keys, indexes and static columns: %s" % (name))

        # Process Dynamic Operator Based Queries Based on r()
        for value in arguments: 
            if not isinstance(value, Operator):
                raise CqlQueryException("You must provide an Operator for the arguments")
            if isinstance(value, disallowed):
                raise CqlQueryException("You cannot use %s in a WHERE clause" % value)
            if not value.left:
                raise CqlQueryException("You must provide a LHS value for the operator")
            if value.right is None:
                raise CqlQueryException("You must provide a RHS value for the operator")

            validate(value.left)
            value.entity = self.entity
            part = str(value)
            results[value.left] = part 
        #Process keyword arguments to create operators, if necessary
        for name, value in keywords.items():    
            validate(name)
            if isinstance(value, Operator):
                if value.right is None:
                    raise ValueError(
                        "Your Operator must have its RHS set to be valid"
                    )
                if isinstance(value, disallowed):
                    raise CqlQueryException("You cannot use %s in a WHERE clause" % value)
                operator = value
                operator.entity = self.entity
                operator.left = name
                part = str(operator)
                results[name] = part
            else:
                # If the user did not specify an operator, use the EQ operator
                operator = EQ(right=value)
                operator.left = name
                operator.entity = self.entity
                part = str(operator)
                results[name] = part  
        return results

    def columns(self) -> bool:
        """The columns that are targeted in this where clause"""
        for name, value in self.keywords.items():
            yield name  

    def _build_(self):
        """Generate CQL from keyword arguments"""
        from cqlalchemy.core.models import Key
        result, started = "", False
        # Process the keys first, and in order (partition keys, then composite, then clustering keys)
        if self.keywords:
            key = Key.create(self.entity)
            where = copy.deepcopy(self.keywords)
            for name in key.parts:
                if name in where:
                    part = where.pop(name)
                    if not started:
                        result += "WHERE {part}".format(part=part)
                        started = True
                    else:
                        result += " AND {part}".format(part=part)
            # Process secondary indexes next, and return the build
            for name, value in where.items():
                if not started:
                    result += "WHERE {part}".format(part=value)
                    started = True
                else:
                    result += " AND {part}".format(part=value)
            return result
        else:
            return ""

    def convert(self):
        """Implement the conversion routine for Predicates"""
        output = self._build_()
        return output

    def __str__(self):
        return self.convert()


class Column(object):
    """A column term in CQL which supports rich expressions"""

    def __init__(self, name:str, entity:"Entity"=None):
        self.name = name
        self.entity = entity
        self.key = None

    def __getitem__(self, key) -> Self:
        """Supports container type access like: column["name"]"""
        self.key = key 
        return self
    
    def __ne__(self, other) -> "Operator":
        """Generate the != operator"""
        if other is None:
            raise CompositionException("CQL does not support the 'NOT NULL' expression")
        op = NEQ(other)
        op.left = self.name
        op.column = self
        return op
    
    def __eq__(self, other):
        """Generate the == operator"""
        if other is None:
            op = NULL(other)
        else:
            op = EQ(other)
        op.left = self.name
        op.column = self
        return op 
    
    def __gt__(self, other):
        """Generate the > operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        op = GT(other)
        op.left = self.name
        op.column = self
        return op 
    
    def __lt__(self, other):
        """Generate the < operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        op = LT(other)
        op.left = self.name
        op.column = self
        return op 
    
    def __ge__(self, other):
        """Generate the >= operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        op = GE(other)
        op.left = self.name
        op.column = self
        return op 
    
    def __matmul__(self, other):
        """Generate the IN operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        if isinstance(other, (list, tuple, set)):
            other = list(other)
            op = IN(*other)
        else:
            op = IN(other)
        op.left = self.name
        op.column = self
        return op 
    
    def __le__(self, other):
        """Generate the <= operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        op = LE(other)
        op.left = self.name 
        op.column = self
        return op 
    
    def convert(self) -> str:
        """Implement the conversion for the key/index supplied to this Column"""
        from cqlalchemy.core.commons import Map, List

        if getattr(self, "entity", None) is None:
            raise ValueError("Provide an Entity to proceed")
        if self.key is None:
            raise ValueError("Provide an index key to access the container")

        property = self.entity.__fields__.get(self.name, None)
        if not property:
            raise ValueError(f"{self.name} is not a valid property on the Entity")
        if not isinstance(property, (Map, List)):
            raise ValueError("Only types List or Map can be indexed")

        if isinstance(property, Map):
            descriptor = property.converter[0]
            return descriptor.convert(value=self.key)  # Normal Conversion.
        else: 
            # Lists expect an int index, conversion is not necessary. 
            if not isinstance(self.key, int):
                raise ValueError("[] index must be an integer")
            return self.key

    def __str__(self):
        if self.key is not None:
            return f"{self.name}[{self.convert()}]"
        return f"{self.name}"


"""
Operator:
Represents and provides comparison operators for CQL queries that understand Models and descriptors.

class Author(Model):
    name = String(index=True)

class Book(Model):
    name = String(key=True)
    price = Float(index=True, required=True)
    author = Reference(Author, index=True, required=True)
    
# You can do queries like:

author = Author.objects.where(name="Leo Tolstoy").get()
book = Book.objects.where(author=author).first() 

# Or even:

author = Author.objects.where(r("name") != "Leo Tolstoy").get()
book = Book.objects.where(r("author") == author).first() 

"""


class Operator(object):
    """The Base Operator that all filters inherit from."""
    column: Optional["Column"] = None
    variable: Optional["Variable"] = None

    def __init__(self, right):
        """Every operator should atleast provide the RHS"""
        self.right = right
        self.column = None 
        self.variable = None
    
    def validate(self):
        """Verifies that this operator is complete"""
        required = ["left", "entity", "right"]
        for name in required:
            if not hasattr(self, name):
                raise ValueError(
                    "Operator is not complete, cannot be used for conversion"
                )

    def convert(self):
        """Generic implementation for the conversion routine."""
        from cqlalchemy.core.commons import Map, List, Set

        self.validate()                             # Validate the operator to make it is complete.
        if self.column:                             # Compute the LHS
            self.column.entity = self.entity        # Help columns find their entity because 'row' or 'r' cannot automatically discover them.
            lhs = str(self.column)
        elif self.variable:
            lhs = str(self.variable)
        else:
            lhs = self.left

        if self.variable:                            # Compute the RHS
            if not self.variable.column():
                if self.right is not None:
                    raise CompositionException(
                        "Right operand must be 'None'"
                        "because you are comparing against the entity directly"
                    )
                return lhs, None 
            else:
                left = self.variable.column()
        elif self.column:
            left = self.left
        else:
            left = self.left
        
        property = self.entity.__fields__.get(left, None)
        if not property:
            raise ValueError(f"{left} is not a property or descriptor on the model")
        if (hasattr(property, "key") and property.key) or property.indexed():
            if isinstance(property, Map):
                converter = property.converter[0]
                right = converter.convert(value=self.right)
            elif isinstance(property, (List, Set)):
                converter = property.converter
                right = converter.convert(value=self.right)
            else:
                right = property.convert(self.entity, self.right)  # Normal Conversion.
            return lhs, right
        else:
            raise ValueError(
                "Operands must be a partition key, clustering key or an indexed property"
            )

    def __and__(self, other):
        """Converts the & bitwise operator to the 'AND' operator in CQL"""
        if isinstance(other, Operator):
            op = AND(self, other)
            return op 
        else:
            raise ValueError("The RHS of a filter has to be an Operator")

    def __or__(self, other):
        """Converts the | bitwise operator to the 'IN' operator in CQL"""
        if isinstance(other, Operator):
            if self.left and other.left:
                if other.left != self.left:
                    raise ValueError("The LHS of both operators must be the same")
            values = [self.right, other.right]
            op = IN(*values)
            op.left = self.left
            return op 
        else:
            raise ValueError("The RHS of a filter has to be an Operator")

    def __str__(self):
        raise NotImplemented("Implemented in subclasses")

class CONTAINS(Operator):
    """Implements `CONTAINS KEY`, and `CONTAINS` filtering"""

    def __init__(self, right=None, key=False):
        self.right = right
        self.key = key

    def convert(self):
        from cqlalchemy.core.commons import Map, List, Set

        required = ["left", "entity", "right"]
        for name in required:
            if not hasattr(self, name):
                raise ValueError(
                    "This Operator is not complete, so cannot be used for conversion"
                )
        if not (self.key or self.right):
            raise ValueError(
                "This Operator is not complete, you must provide the `key` or `right` paramater"
            )
        if not isinstance(self.left, str):
            raise ValueError(
                "The LHS of CONTAINS filter has to be a valid property name"
            )
        property = self.entity.__fields__.get(self.left, None)
        if not property:
            raise ValueError("{self.left} is not a property".format(self=self))
        if property.indexed():
            if isinstance(property, Map):
                if self.key:
                    converter = property.converter[0]
                    value = converter.convert(self.entity, self.right)
                    return (self.left, value)
                else:
                    converter = property.converter[1]
                    value = converter.convert(self.entity, self.right)
                    return (self.left, value)
            elif isinstance(property, (List, Set)):
                converter = property.converter
                value = converter.convert(self.entity, self.right)
                return (self.left, value)
            else:
                raise ValueError(
                    "You may only use the `CONTAINS` filter on Collections"
                )
        else:
            raise ValueError("Operands must be an indexed collection")

    def __str__(self):
        """Implementation for the Model.objects.where(entries=CONTAINS(key=`name`))"""
        left, right = self.convert()
        if self.key:
            return "{left} CONTAINS KEY {right}".format(left=left, right=right)
        else:
            return "{left} CONTAINS {right}".format(left=left, right=right)

class NULL(Operator):
    "Represents the 'NULL' operator in CQL"

    def validate(self):
        """Verifies that this operator is complete"""
        required = ["left",]
        for name in required:
            if not hasattr(self, name):
                raise ValueError(
                    "Operator is not complete, cannot be used for conversion"
                )

    def convert(self):
        """Generic implementation for the conversion routine."""
        self.validate()                             # Validate the operator to make it is complete.
        if self.column:                             # Compute the LHS
            self.column.entity = self.entity        # Help columns find their entity because 'row' or 'r' cannot automatically discover them.
            lhs = str(self.column)
        elif self.variable:
            lhs = str(self.variable)
        else:
            lhs = self.left
        return lhs, None

    def __str__(self):
        """Implementation for the Model.objects.where(name="Hello") operand"""
        left, right = self.convert()
        return "{left} IS NULL".format(left=left)

class NOTNULL(Operator):
    "Represents the 'NOT NULL' operator in CQL"

    def validate(self):
        """Verifies that this operator is complete"""
        required = ["left",]
        for name in required:
            if not hasattr(self, name):
                raise ValueError(
                    "Operator is not complete, cannot be used for conversion"
                )

    def convert(self):
        """Generic implementation for the conversion routine."""
        self.validate()                             # Validate the operator to make it is complete.
        if self.column:                             # Compute the LHS
            self.column.entity = self.entity        # Help columns find their entity because 'row' or 'r' cannot automatically discover them.
            lhs = str(self.column)
        elif self.variable:
            lhs = str(self.variable)
        else:
            lhs = self.left
        return lhs, None

    def __str__(self):
        """Implementation for the Model.objects.where(name="Hello") operand"""
        left, right = self.convert()
        return "{left} IS NOT NULL".format(left=left)

class EQ(Operator):
    "Represents the '=' operator in CQL"

    def __str__(self):
        """Implementation for the Model.objects.where(name="Hello") operand"""
        left, right = self.convert()
        return "{left} = {right}".format(left=left, right=right)

class NEQ(Operator):
    "Represents the '!=' operator in CQL"

    def __str__(self):
        """Implementation for the Model.objects.where(name="Hello") operand"""
        left, right = self.convert()
        return "{left} != {right}".format(left=left, right=right)

class LT(Operator):
    "Represents the '<' CQL Operator"

    def __str__(self):
        left, right = self.convert()
        return "{left} < {right}".format(left=left, right=right)

class GT(Operator):
    "Represents the '>' CQL operation"

    def __str__(self):
        left, right = self.convert()
        return "{left} > {right}".format(left=left, right=right)

class LE(Operator):
    "Represents the '<=' operator in CQL"

    def __str__(self):
        left, right = self.convert()
        return "{left} <= {right}".format(left=left, right=right)

class GE(Operator):
    "Represents the '>=' operator in CQL"

    def __str__(self):
        left, right = self.convert()
        return "{left} >= {right}".format(left=left, right=right)

class AND(Operator):
    "Represents an operator that joins two or more Operations with an AND clause"

    def __init__(self, *operators):
        for operator in operators:
            if not isinstance(operator, Operator):
                raise ValueError("Operands must be valid operators")
        self.right = operators

    def convert(self):
        required = ["left", "entity", "right"]
        for name in required:
            if not hasattr(self, name):
                raise ValueError(
                    "This Operator is not complete, so cannot be used for conversion"
                )

        property = self.entity.__fields__.get(self.left, None)
        if not property:
            raise ValueError(f"{self.left} is not a property")
        if (hasattr(property, "key") and property.key) or property.indexed():
            results = []
            for operator in self.right:
                operator.left = self.left
                operator.entity = self.entity
                part = str(operator)
                results.append(part)
            return results
        else:
            raise ValueError(
                "Operands must be a partition key, clustering key or an indexed property"
            )

    def __str__(self):
        results = self.convert()
        return " AND ".join(results)

class IN(Operator):
    "Represents the 'IN' operator in CQL"

    def __init__(self, *right):
        for value in right:
            if value is None:
                raise CompositionException("IN operator cannot contain None")
        self.right = right

    def convert(self):
        """Converts all the items in the IN operator"""
        if not bool(
            hasattr(self, "left") and hasattr(self, "entity") and hasattr(self, "right")
        ):
            raise ValueError("This Operator isn't complete.")
        
        property = self.entity.__fields__.get(self.left, None)
        if not property:
            raise ValueError("{self.left} is not an indexed property".format(self=self))
        if (hasattr(property, "key") and property.key) or property.indexed():
            left = self.left
            converted = []
            for value in self.right:
                v = property.convert(self.entity, value)
                converted.append(v)
            return left, converted
        else:
            raise ValueError(
                "Operands must be an id, clustering key or an indexed property"
            )

    def __str__(self):
        left, right = self.convert()
        right = ", ".join(right)
        return "{left} IN ({right})".format(left=left, right=right)



"""
Implementation for the raw underlying transaction fluent API

```python
transfer = Transaction()
person = transfer.variable("person", select(Account).column("credits").where(id=account.id))
photo = transfer.variable("photo", select(Photo).where(profile=account.profile))
transfer\
    .condition(photo != None and person.credits == 0)\
        .then(update(Account).incr("credits", amount).where(id=account.id))\
        .then(update(Profile).set(active=True).where(id=account.profile))\
    .end()\
.add(insert(Notification).values(user=profile.id, text="You have been rewarded with credits"))\
.commit()
print("Transaction was successfully executed")
```
"""

class Variable(object):
    """Variable for use in Transactions"""
    _entity_: "Entity"
    _key_: str 
    _attribute_: str 
    _transaction_: "Transaction"
    _query_: "SelectQuery"
    _name_: str 

    def __init__(self, transaction:"Transaction", name:str, query:"SelectQuery", entity:"Entity"):
        if not name:
            raise ValueError("Variable name cannot be empty")
        if not query:
            raise ValueError("Query cannot be empty")
        if not transaction:
            raise ValueError("Transaction cannot be empty")
        if not entity:
            raise ValueError("Entity cannot be empty")
        self._name_ = name
        self._query_ = query
        self._transaction_ = transaction
        self._entity_ = entity 
        self._key_ = None 
        self._attribute_ = None 
    
    def __getitem__(self, key) -> Self:
        """Supports container type access like: variable.attribute["name"]"""
        self._key_ = key 
        return self
    
    def __getattr__(self, name):
        """Supports attribute access like: variable.attribute"""
        if getattr(self, "_attribute_") is not None :
            var = Variable(
                getattr(self, "_transaction_"),
                getattr(self, "_name_"),
                getattr(self, "_query_"),
                getattr(self, "_entity_")
            )
            var = getattr(var, name)
            return var
        else:
            self._attribute_ = name 
            return self
    
    def __ne__(self, other) -> "Operator":
        """Generate the != operator"""
        if other is None:
            op = NOTNULL(other)
        else:
            op = NEQ(other)
        op.left = self._attribute_
        op.variable = self
        op.entity = self._entity_
        return op
    
    def __eq__(self, other):
        """Generate the == operator"""
        if other is None:
            op = NULL(other)
        else:
            op = EQ(other)
        op.left = self._attribute_
        op.variable = self
        op.entity = self._entity_
        return op 
    
    def __gt__(self, other):
        """Generate the > operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        op = GT(other)
        op.left = self._attribute_
        op.variable = self
        op.entity = self._entity_
        return op 
    
    def __lt__(self, other):
        """Generate the < operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        op = LT(other)
        op.left = self._attribute_
        op.variable = self
        op.entity = self._entity_
        return op 
    
    def __ge__(self, other):
        """Generate the >= operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        op = GE(other)
        op.left = self._attribute_
        op.variable = self
        op.entity = self._entity_
        return op 
    
    def __matmul__(self, other):
        """Generate the IN operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        if isinstance(other, (list, tuple, set)):
            other = list(other)
            op = IN(*other)
        else:
            op = IN(other)
        op.left = self._attribute_
        op.variable = self
        op.entity = self._entity_
        return op 
    
    def __le__(self, other):
        """Generate the <= operator"""
        if other is None:
            raise CompositionException("You cannot use this operand with 'None'")
        op = LE(other)
        op.left = self._attribute_ 
        op.variable = self
        op.entity = self._entity_
        return op 
    
    def column(self):
        return self._attribute_

    def statement(self):
        """Serializes the Variable to the equivalent CQL Transaction variable definition statement"""
        q = str(self._query_)
        q = q.strip(";")
        query = f"LET {self._name_} = ({q});"
        return query

    def convert(self) -> str:
        """Implement the conversion for the key/index supplied to this Variable"""
        from cqlalchemy.core.commons import Map, List

        if getattr(self, "_entity_", None) is None:
            raise ValueError("Provide an Entity to proceed")
        if self._key_ is None:
            raise ValueError("Provide an index/key to proceed")
        if self._attribute_ is None:
            raise ValueError("Provide an attribute to proceed")

        property = self._entity_.__fields__.get(self._attribute_, None)
        if not property:
            raise ValueError(f"{self._attribute_} is not a valid property on the Entity")
        if not isinstance(property, (Map, List)):
            raise ValueError("Only types List or Map can be indexed")
        if isinstance(property, Map):
            descriptor = property.converter[0]
            return descriptor.convert(value=self._key_)  # Normal Conversion.
        else: 
            # Lists expect an int index, conversion is not necessary. 
            if not isinstance(self._key_, int):
                raise ValueError("[] index must be an int")
            return self._key_

    def __str__(self):
        if self._attribute_ and not self._key_:
            return f"{self._name_}.{self._attribute_}"
        if self._attribute_ and self._key_:
            return f"{self._name_}.{self._attribute_}[{self.convert()}]"
        if not self._attribute_ and self._key_:
            raise CompositionException("You cannot index a variable without an attribute")
        return f"{self._name_}"


class Condition(object):
    """Generates 'IF' predicates for C* Transactions"""

    closed: bool
    statements: List["CqlQuery"] 
    expressions: List["Operator"]
    transaction: "Transaction"

    def __init__(self, transaction:"Transaction"):
        self.transaction = transaction
        self.closed = False 
        self.statements = []
        self.expressions = []

    def then(self, query:"CqlQuery"):
        """Add a query to the condition"""
        if self.closed:
            raise CompositionException("You cannot add queries to a closed condition")
        self.statements.append(query)
        return self

    def end(self) -> "Transaction":
        """Returns the Transaction object"""
        self.closed = True
        return self.transaction

    def statement(self):
        """Convert the condition to a CQL string"""
        if not self.closed:
            raise CompositionException("You cannot convert an open condition to a CQL string")
        started , header = False, ""
        if not self.expressions:
            raise CompositionException("You must provide at least one expression for a condition")
        
        query = """IF{header} THEN\n{statements}\n{ending}"""
        started, header, ending = False, "", "END IF"
        for value in self.expressions:
            if not isinstance(value, Operator):
                raise ValueError("All arguments must be of type Operator")
            value.validate()
            value = str(value)
            if not started:
                header = f" {value}"
                started = True
            else:
                header += f" AND {value}"
        
        statements = "\n".join([str(statement) for statement in self.statements])
        statements = textwrap.indent(statements, " " * 4)
        return query.format(header=header, statements=statements, ending=ending)
    

class Transaction(object):
    """Abstraction for Accord Transactions in Cassandra"""
    guid: uuid.UUID
    keyspace: str
    context: Dict[str, Any]
    variables: List[Variable]
    conditions: List[Condition]
    statements: List[Union[str, "UpdateQuery", "InsertQuery", "DeleteQuery"]]
    
    def __init__(self, keyspace:str, **context):
        """Create a Transaction object"""
        self.guid = uuid.uuid7()
        self.keyspace = keyspace
        self.context = context
        self.variables = []
        self.conditions = []
        self.statements = []
    
    def variable(self, name:str, query:"SelectQuery", entity:"Entity") -> Variable:
        """Create a variable for use in the transaction"""
        variable = Variable(self, name, query, entity)
        self.variables.append(variable)
        return variable
    
    def condition(self, *expressions) -> Condition:
        """Add a condition to the transaction"""
        condition = Condition(self)
        for expression in expressions:
            if not isinstance(expression, Operator):
                raise CompositionException("You must provide an Operator for transaction conditions")
            condition.expressions.append(expression)
        self.conditions.append(condition)
        return condition

    def add(self, query: Union[str, "InsertQuery", "UpdateQuery", "DeleteQuery"]):
        """Add a query to the transaction"""
        if not query:
            raise ValueError("You must provide a query")
        if not isinstance(query, (str, "InsertQuery", "UpdateQuery", "DeleteQuery")):
            raise ValueError("You must provide a valid query")
        self.statements.append(query)

    def execute(self):
        """Serializes and executes the Transaction over the wire"""
        from cqlalchemy.connection.cql import execute
        try:
            if not self.conditions and not self.statements:
                raise CompositionException("Transaction Empty: No Statements to Execute")

            query = """BEGIN TRANSACTION\n{variables}{conditions}{statements}COMMIT TRANSACTION;"""
            if self.statements:
                statements = "\n".join([str(statement) for statement in self.statements])
                statements = textwrap.indent(statements, " " * 4)
                statements += "\n"
            else:
                statements = ""
            if self.variables:
                variables = "\n".join([variable.statement() for variable in self.variables])
                variables = textwrap.indent(variables, " " * 4)
                variables += "\n"
            else:
                variables = ""
            if self.conditions:
                conditions = "\n".join([condition.statement() for condition in self.conditions])
                conditions = textwrap.indent(conditions, " " * 4)
                conditions += "\n"
            else:
                conditions = ""
            query = query.format(statements=statements, variables=variables, conditions=conditions)
            self.results = execute(query, keyspace=self.keyspace)
            self.open = False
        except Exception as e:
            self.exception = e
            self.error = True
            self.open = False
            raise e
        finally:
            self.run = True 
        