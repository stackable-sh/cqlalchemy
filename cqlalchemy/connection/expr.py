from typing import Self, Optional
from multidict import MultiDict


class Functor(object):
    """An object marker for supported CQL functions"""

    def __init__(self, part: str):
        self.part = part

    def __call__(self, *arguments, **keywords):
        return self.part

    def __str__(self):
        return self.part


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
    """An CQL Expression Composer"""

    def __init__(self, *arguments, **keywords):
        self.arguments = arguments
        self.keywords = MultiDict(**keywords)

    def convert(self):
        """Implement the conversion routine for Predicates"""
        if not hasattr(self, "entity"):
            raise ValueError("You need to set Entity for this Predicate to use it")

        started, output = False, ""
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

    def __str__(self):
        return self.convert()


class Column(object):
    """A column term in CQL"""

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
        op = NEQ(other) if other is not None else NOTNULL()
        op.left = self.name
        op.column = self
        return op
    
    def __eq__(self, other):
        """Generate the == operator"""
        op = EQ(other) if other is not None else NULL()
        op.left = self.name
        op.column = self
        return op 
    
    def __gt__(self, other):
        """Generate the > operator"""
        op = GT(other)
        op.left = self.name
        op.column = self
        return op 
    
    def __lt__(self, other):
        """Generate the < operator"""
        op = LT(other)
        op.left = self.name
        op.column = self
        return op 
    
    def __ge__(self, other):
        """Generate the >= operator"""
        op = GE(other)
        op.left = self.name
        op.column = self
        return op 
    
    def __matmul__(self, other):
        """Generate the IN operator"""
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
        op = LE(other)
        op.left = self.name 
        op.column = self
        return op 
    
    def convert(self) -> str:
        """Implement the conversion for the key/index supplied to this Column"""
        from ..core.commons import Map, List

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
    column: Optional[Column] = None

    def __init__(self, right):
        """Every operator should atleast provide the RHS"""
        self.right = right
        self.column = None 

    def convert(self):
        """Generic implementation for the conversion routine."""
        from ..core.commons import Map, List, Set

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
            if self.column:
                self.column.entity = self.entity 
                left = str(self.column)
            else:
                left = self.left 
            if isinstance(property, Map):
                converter = property.converter[0]
                right = converter.convert(value=self.right)
            elif isinstance(property, (List, Set)):
                converter = property.converter
                right = converter.convert(value=self.right)
            else:
                right = property.convert(self.entity, self.right)  # Normal Conversion.
            return left, right
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

    def __str__(self):
        """Implementation for the Model.objects.where(name="Hello") operand"""
        left, right = self.convert()
        return "{left} == NULL".format(left=left)

class NOTNULL(Operator):
    "Represents the 'NOT NULL' operator in CQL"

    def __str__(self):
        """Implementation for the Model.objects.where(name="Hello") operand"""
        left, right = self.convert()
        return "{left} != NULL".format(left=left)

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
