
from typing import Any
from cqlalchemy.core.builtins import assertNonNull, assertType

"""Scalar & Aggregate CQL functions to enrich queries"""


class Function(object):
    """An object marker for supported CQL functions"""

    def __init__(self, part):
        self.part = part

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self.part 
    
    def __str__(self) -> str:
        return self()
    

def ttl(name, alias=None):
    """TTL CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Function(f"TTL({name}) AS {alias}")

def writetime(name, alias=None):
    """WRITETIME CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Function(f"WRITETIME({name}) AS {alias}")

def avg(name, alias=None):
    """AVG CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Function(f"AVG({name}) AS {alias}")

def sum(self, name, alias=None):
    """SUM CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Function(f"SUM({name}) AS {alias}")

def max(name, alias=None):
    """MAX CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Function(f"MAX({name}) AS {alias}")

def min(name, alias=None):
    """MIN CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Function(f"MIN({name}) AS {alias}")

def count(name, alias=None):
    """COUNT CQL function on @name"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    alias = name.lower() if not alias else alias
    return Function(f"COUNT({name}) AS {alias}")


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

query = Author.objects.where(name="Leo Tolstoy")
result = query.execute()

author = result.one()
book = Book.objects.where(author=author).first() 

"""
class Operator(object):
    '''The Base Operator that all filters inherit from.'''
    def __init__(self, right):
        '''Every operator should atleast provide the RHS'''
        self.right = right
        
    def convert(self):
        '''Generic implementation for the conversion routine.'''
        if not bool(hasattr(self, "left") and hasattr(self, "model") and hasattr(self, "right")):
            raise ValueError("This Operator isn't complete.")
        if not isinstance(self.left, str):
            raise ValueError("The LHS of a EQ query has to be a valid property name")
        property = self.model.__fields__.get(self.left, None)
        if not property:
            raise ValueError("{self.left} is not a property".format(self=self))
        if property.name != "id" and not property.key and not property.indexed():
            raise ValueError("Operands must be an id, clustering key or an indexed property")
        left = self.left
        right = property.convert(self.model, self.right) #Normal Conversion.
        return left, right
    
    def __str__(self):
        raise NotImplemented("Implemented in subclasses")

   
class EQ(Operator):
    "Represents the '=' operator in CQL"
    
    def __str__(self):
        """Implementation for the Model.objects.where(name="Hello") operand"""
        left, right = self.convert()
        return "{left} = {right}".format(left=left, right=right)


class LT(Operator):
    "Represents the '<' CQL Operator"
    
    def __str__(self):
        "Implementation for the Model.objects.where(price=LT(20))"
        left, right = self.convert()
        return "{left} < {right}".format(left=left, right=right)


class GT(Operator):
    "Represents the '>' CQL operation"
    
    def __str__(self):
        "Implementation for the Model.objects.where(price=GT(10))"
        left, right = self.convert()
        return "{left} > {right}".format(left=left, right=right)


class LTE(Operator):
    "Represents the '<=' operator in CQL"
    
    def __str__(self):
        '''Implementation for the Model.objects.where(price=LTE(25)) operand'''
        left, right = self.convert()
        return "{left} <= {right}".format(left=left, right=right)


class GTE(Operator):
    "Represents the '>=' operator in CQL"
    
    def __str__(self):
        '''Implementation for the Model.objects.where(name=GTE(10))'''
        left, right = self.convert()
        return "{left} >= {right}".format(left=left, right=right)


class IN(Operator):
    "Represents the 'IN' operator in CQL"
    
    def __init__(self, *right):
        '''Every operator should atleast provide the LHS'''
        self.right = right
    
    def convert(self):
        '''Converts all the items in the IN operator'''
        if not bool(hasattr(self, "left") and hasattr(self, "model") and hasattr(self, "right")):
            raise ValueError("This Operator isn't complete.")
        if not isinstance(self.left, str):
            raise ValueError("The LHS of a EQ query has to be a valid property name")
        property = self.model.__fields__.get(self.left, None)
        if not property:
            raise ValueError("{self.left} is not an indexed property".format(self=self))
        if property.name != "id" and not property.key and not property.indexed():
            raise ValueError("Operands must be an id, clustering key or an indexed property")
        left = self.left
        converted = []
        for value in self.right:
            v = property.convert(self.model, value)
            converted.append(v)
        return left, converted
        
    def __str__(self):
        '''Implementation for the Model.objects.where(name=IN(1,2,3))'''
        left, right = self.convert()
        right = ", ".join(right)
        return "{left} IN ({right})".format(left=left, right=right)