import textwrap
from typing import Self, Optional

from multidict import MultiDict

from cqlalchemy.core.builtins import assertNonNull, assertType
from cqlalchemy.connection.cql import CqlQueryException, IllegalStateException

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
    """An expression Composer for rich, idiomatic cql queries in python"""

    def __init__(self, *arguments, **keywords):
        self.arguments = arguments
        self.keywords = MultiDict(**keywords)

    def _keywords_(self, output:str, started:bool):
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
    
    def _arguments_(self, output:str, started:bool):
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
        started, output = False, ""
        output, started = self._arguments_(output, started)
        output = self._keywords_(output, started)
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
                    "Operator is not complete, cannot be used for conversion"
                )

        property = self.entity.__fields__.get(self.left, None)
        if not property:
            raise ValueError(f"{self.left} is not a property")
        if (hasattr(property, "key") and property.key) or property.indexed():
            if self.column:
                self.column.entity = self.entity 
                left = str(self.column)
            if self.variable:
                self.variable.entity = self.entity 
                left = str(self.variable)
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
    entity: "Entity"
    key: str 
    attribute: str 

    def __init__(self, name:str, query:SelectQuery, transaction:"Transaction", entity:"Entity"=None):
        if not name:
            raise ValueError("Variable name cannot be empty")
        if not query:
            raise ValueError("Query cannot be empty")
        if not transaction:
            raise ValueError("Transaction cannot be empty")
        self.name = name
        self.query = query
        self.transaction = transaction
        self.entity = entity 
        self.key = None 
        self.attribute = None 
    
    def __getitem__(self, key) -> Self:
        """Supports container type access like: variable.attribute["name"]"""
        self.key = key 
        return self
    
    def __getattribute__(self, name):
        """Supports attribute access like: variable.attribute"""
        self.attribute = name 
        return self
    
    def __ne__(self, other) -> "Operator":
        """Generate the != operator"""
        op = NEQ(other) if other is not None else NOTNULL()
        op.left = self.name
        op.variable = self
        return op
    
    def __eq__(self, other):
        """Generate the == operator"""
        op = EQ(other) if other is not None else NULL()
        op.left = self.name
        op.variable = self
        return op 
    
    def __gt__(self, other):
        """Generate the > operator"""
        op = GT(other)
        op.left = self.name
        op.variable = self
        return op 
    
    def __lt__(self, other):
        """Generate the < operator"""
        op = LT(other)
        op.left = self.name
        op.variable = self
        return op 
    
    def __ge__(self, other):
        """Generate the >= operator"""
        op = GE(other)
        op.left = self.name
        op.variable = self
        return op 
    
    def __matmul__(self, other):
        """Generate the IN operator"""
        if isinstance(other, (list, tuple, set)):
            other = list(other)
            op = IN(*other)
        else:
            op = IN(other)
        op.left = self.name
        op.variable = self
        return op 
    
    def __le__(self, other):
        """Generate the <= operator"""
        op = LE(other)
        op.left = self.name 
        op.variable = self
        return op 
    
    def statement(self):
        """Serializes the Variable to the equivalent CQL Transaction variable definition statement"""
        query = f"LET {self.name} = ({self.query});"
        return query

    def convert(self) -> str:
        """Implement the conversion for the key/index supplied to this Variable"""
        from ..core.commons import Map, List

        if getattr(self, "entity", None) is None:
            raise ValueError("Provide an Entity to proceed")
        if self.key is None:
            raise ValueError("Provide an index/key to proceed")
        if self.attribute is None:
            raise ValueError("Provide an attribute to proceed")

        property = self.entity.__fields__.get(self.attribute, None)
        if not property:
            raise ValueError(f"{self.attribute} is not a valid property on the Entity")
        if not isinstance(property, (Map, List)):
            raise ValueError("Only types List or Map can be indexed")
        if isinstance(property, Map):
            descriptor = property.converter[0]
            return descriptor.convert(value=self.key)  # Normal Conversion.
        else: 
            # Lists expect an int index, conversion is not necessary. 
            if not isinstance(self.key, int):
                raise ValueError("[] index must be an int")
            return self.key

    def __str__(self):
        if self.attribute and not self.key:
            return f"{self.name}.{self.attribute}"
        if self.attribute and self.key:
            return f"{self.name}.{self.attribute}[{self.convert()}]"
        return f"{self.name}"


class Condition(object):
    """Generates 'IF' predicates for C* Transactions"""

    closed: bool
    statements: List[CqlQuery] 
    expressions: List[Expression]
    transaction: "Transaction"

    def __init__(self, transaction:"Transaction"):
        self.transaction = transaction
        self.closed = False 
        self.statements = []
        self.expressions = []

    def then(self, query:CqlQuery):
        """Add a query to the condition"""
        if self.closed:
            raise CqlQueryException("You cannot add queries to a closed condition")
        self.statements.append(query)
        return self

    def end(self) -> "Transaction":
        """Returns the Transaction object"""
        self.closed = True
        return self.transaction

    def statement(self):
        """Convert the condition to a CQL string"""
        if not self.closed:
            raise CqlQueryException("You cannot convert an open condition to a CQL string")
        started , header = False, ""
        if not self.expressions:
            raise CqlQueryException("You must provide at least one expression for a condition")
        if not hasattr(self, "entity"):
            raise ValueError("You need to set Entity for this Condition to use it")
        
        query = """{header}\n{statements}\n{ending}"""
        started, header, ending = False, "", "END IF"
        for value in self.expressions:
            if not isinstance(value, Operator):
                raise ValueError("All arguments must be of type Operator")
            if value.right is None:
                raise ValueError("Your Operator must have its RHS set to be valid")
            if value.left is None:
                raise ValueError("Your Operator must have its LHS set to be valid")
            value.entity = self.entity
            value = str(value)
            if not started:
                header = f" IF {value}"
                started = True
            else:
                header += f" AND {value}"
        
        statements = "\n".join([statement.text() for statement in self.statements])
        statements = textwrap.indent(statements, " " * 4)
        return query.format(header=header, statements=statements, ending=ending)
    

class Transaction(threading.local):
    """Abstraction for Accord Transactions in Cassandra"""
    keyspace: str
    context: Dict[str, Any]
    variables: List[Variable]
    conditions: List[Condition]
    statements: List[Union[str, "UpdateQuery", "InsertQuery", "DeleteQuery"]]
    
    def __init__(self, keyspace:str, **context):
        """Create a Transaction object"""
        self.guid = uuid.uuid4()
        self.keyspace = keyspace
        self.context = context
        self.variables = []
        self.conditions = []
        self.statements = []
        
    def variable(self, name:str, query:SelectQuery, entity:"Entity"=None) -> Variable:
        """Create a variable for use in the transaction"""
        variable = Variable(name, query, self, entity)
        self.variables.append(variable)
        return variable
    
    def condition(self, *expressions) -> Condition:
        """Add a condition to the transaction"""
        condition = Condition(self)
        for expression in expressions:
            if not isinstance(expression, Operator):
                raise CqlQueryException("You must provide an Operator for transaction conditions")
            condition.expressions.append(expression)
        self.conditions.append(condition)
        return condition

    def execute(self):
        """Serializes and executes the Transaction over the wire"""
        try:
            if not self.open:
                raise IllegalStateException(
                    f"Transaction: {self.guid} must be open and ready for use before you can `execute`"
                )

            if not self.conditions and not self.statements:
                raise CqlQueryException("Transaction Empty: No Statements to Execute")

            query = """BEGIN TRANSACTION\n{variables}\n{conditions}\n{statements}\nCOMMIT;"""
            statements = "\n".join([statement.text() for statement in self.statements])
            statements = textwrap.indent(statements, " " * 4)

            variables = "\n".join([variable.statement() for variable in self.variables])
            variables = textwrap.indent(variables, " " * 4)

            conditions = "\n".join([condition.statement() for condition in self.conditions])
            conditions = textwrap.indent(conditions, " " * 4)
            
            query = query.format(statements=statements, variables=variables, conditions=conditions)
            print(query)
           
            self.results = execute(query, keyspace=self.keyspace)
            print("*" * 100)
            print(self.results)
            print("*" * 100)
            self.open = False
        except Exception as e:
            self.exception = e
            self.error = True
            self.open = False
            raise e
        finally:
            self.run = True 
        