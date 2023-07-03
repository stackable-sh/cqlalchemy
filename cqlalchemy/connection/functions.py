"""Scalar & Aggregate CQL functions to enrich queries"""

from cqlalchemy.core.builtins import assertNonNull, assertType


class Function(object):
    """An object marker for supported CQL functions"""
    def __init__(self, part:str):
        self.part = part

    def __call__(self, *arguments, **keywords):
        return self.part 
    
    def __str__(self):
        return self.part
    
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

def sum(name, alias=None):
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


class Predicate(object):
    """Provides support for conditional updates in C*"""

    def __init__(self, **keywords):
        self.conditions = dict()
        for name, value in keywords.items():
            self.conditions[name] = value
    
    def convert(self):
        '''Implement the conversion routine for Predicates'''
        if not hasattr(self, "entity"):
            raise ValueError("You need to set Entity for this Predicate to use it")
        
        started, output = False, ""
        for name, value in self.conditions.items():
            property = self.entity.__fields__.get(name, None)
            if not property:
                raise ValueError("There is no field named: %s" % name)
            value = property.convert(self.entity, value)
            if not started:
                output = f" IF {name}={value}"
                started = True
            else:
                output += f" AND {name}={value}"
        return output
    
    def __str__(self):
        return self.convert()


"""
when

Syntatic sugar for creating and using Predicate for LWT and Conditional Updates. 
You can use `when` whenever a Predicate is required by cqlalchemy.

```python
class Author(Model):
    name = String(index=True)
    bio = String(index=True, required=True)

author = Author.create(name="Walter Isaacson", bio="I write autobiographies")
assert author.name == "Walter Isaacson"

author = Author.upsert(name="Charles Dickens", predicate=when(name="Walter Isaacson"))
assert author.name == "Charles Dickens"
assert Author.objects.count() == 1
```
"""
def when(**keywords):
    """Shortcute for creating Predicate objects"""
    return Predicate(**keywords)

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

"""
class Operator(object):
    '''The Base Operator that all filters inherit from.'''
    def __init__(self, right):
        '''Every operator should atleast provide the RHS'''
        self.right = right
        
    def convert(self):
        '''Generic implementation for the conversion routine.'''
        required = ["left", "entity", "right"]
        for name in required:
            if not hasattr(self, name):
                raise ValueError("This Operator is not complete, so cannot be used for conversion")
        if not isinstance(self.left, str):
            raise ValueError("The LHS of a filter has to be a valid property name")
        property = self.entity.__fields__.get(self.left, None)
        if not property:
            raise ValueError(f"{self.left} is not a property")
        if (hasattr(property, "key") and property.key) or property.indexed():
            left = self.left
            right = property.convert(self.entity, self.right) #Normal Conversion.
            return left, right
        else:
            raise ValueError("Operands must be a partition key, clustering key or an indexed property")
    
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
                raise ValueError("This Operator is not complete, so cannot be used for conversion")
        if not (self.key or self.right):
            raise ValueError("This Operator is not complete, you must provide the `key` or `right` paramater")
        if not isinstance(self.left, str):
            raise ValueError("The LHS of CONTAINS filter has to be a valid property name")
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
                raise ValueError("You may only use the `CONTAINS` filter on Collections")
        else:
            raise ValueError("Operands must be an indexed collection")   
    
    def __str__(self):
        """Implementation for the Model.objects.where(entries=CONTAINS(key=`name`))"""
        left, right = self.convert()
        if self.key:
            return "{left} CONTAINS KEY {right}".format(left=left, right=right)
        else:
            return "{left} CONTAINS {right}".format(left=left, right=right)

            
   
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
        if not bool(hasattr(self, "left") and hasattr(self, "entity") and hasattr(self, "right")):
            raise ValueError("This Operator isn't complete.")
        if not isinstance(self.left, str):
            raise ValueError("The LHS of a EQ query has to be a valid property name")
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
            raise ValueError("Operands must be an id, clustering key or an indexed property")
        
    def __str__(self):
        '''Implementation for the Model.objects.where(name=IN(1,2,3))'''
        left, right = self.convert()
        right = ", ".join(right)
        return "{left} IN ({right})".format(left=left, right=right)