
from contextlib import contextmanager as manager
from typing import Dict, Any, Union, List, Callable
import threading

from cqlalchemy.options import keyspace as keyspace_
from cqlalchemy.core.builtins import Local, IllegalStateException
from cqlalchemy.connection.cql.expr import Operator, Variable, Transaction, Condition
from cqlalchemy.connection.cql import SelectQuery, InsertQuery, UpdateQuery, DeleteQuery, CqlQueryException


"""

```python

# ORM Style
account, profile, photo = None, None, None
try:
    atom = Atom()
    pointer = Pointer(Profile, id="98e50d75-d025-4d4d-b99f-e08024ac44ec")
    with atom:
        person = atom.var(pointer)
        with atom.when(person.website == None):
            profile = Profile.create(name="John Doe", email="john.doe@example.com", phone="1234567890")
            account = Account.create(password="password", profile=profile)
            photo = Photo.create(profile=profile, blob=photo)
            Notification.create(user=profile.id, text=f"Welcome {profile.name}")

        # Add some more operations into the transaction, outside the conditional block
        author["name"] = "John Doe"
        author["email"] = "john.doe@example.com"
        author["phone"] = "1234567890"
        author["age"] = 30
        author["active"] = True
        author.save()                                              

except Exception as e:
    raise e
else:
    print("Transaction was successfully executed")
    return account, profile, photo
```
"""

class Atom(threading.local):
    """An atomic (transactional) unit of work which works with your Models"""
    open: bool 
    context: Dict[str, Any]
    transaction: "Transaction"
    
    def __init__(self, keyspace:str=None, **context):
        """Create a Transaction object"""
        self.open = False 
        self.context = context
        self.condition = None
        self.keyspace = keyspace if keyspace is not None else keyspace_()
        self.transaction = Transaction(keyspace=self.keyspace)
        self.callbacks = []
        self.errbacks = []
        self.run = False
        self.thread = threading.get_native_id()
    
    def var(self, value:Union["Pointer", "Entity", SelectQuery], name:str=None) -> Variable:
        """Create a variable for use in the transaction"""
        from cqlalchemy.core.models import Pointer, Entity
        if isinstance(value, Pointer):
            if not value.entity:
                raise ValueError("You must provide an entity for the Pointer")
            query = value.query()
            entity = value.entity 
        elif isinstance(value, Entity):
            if not value.saved():
                raise ValueError("You can only use saved entities as variables")
            query = value.key.query()
            entity = value
        elif isinstance(value, SelectQuery):
            query = value
            entity = value.entity
        else:
            raise ValueError("You must provide a Pointer, Entity or SelectQuery")
        
        if not name:
            name = f"var_{len(self.transaction.variables)}"
        variable = self.transaction.variable(name, query, entity)
        return variable
    
    @manager
    def when(self, *expressions) -> Condition:
        """Add a condition to the transaction"""
        if not self.open:
            raise CqlQueryException("You cannot add conditions to a closed transaction")
        if self.condition and not self.condition.closed:
            raise CqlQueryException("You cannot nest conditional blocks")
        self.condition = self.transaction.condition(*expressions)
        yield self.condition  # Yield to the caller to add queries to the condition
        self.condition.end()
    
    def add(self, query: Union[InsertQuery, UpdateQuery, DeleteQuery]):
        """Add a query to the transaction"""
        if not self.open:
            raise CqlQueryException("You cannot add queries to a closed transaction")
        if not query:
            raise ValueError("You must provide a query")
        if not isinstance(query, (str, InsertQuery, UpdateQuery, DeleteQuery)):
            raise ValueError("You must provide a valid query")
        if self.condition and not self.condition.closed:
            self.condition.then(query)
        else:
            self.transaction.add(query)
    
    @classmethod
    def get(self):
        """Returns the current atom for this thread or None"""
        thread = Local.instance()
        atom = getattr(thread, "atom", None)
        return atom

    def set(self):
        """Attempt to set this transaction as the transaction for the current thread"""
        if self.get():
            raise IllegalStateException("You cannot have two active Transaction objects in a thread")
        self.open = True
        thread = Local.instance()
        thread.atom = self

    def unset(self):
        """Attempt to unset this transaction as the transaction for the current thread"""
        atom = self.get()
        if atom != self:
            raise IllegalStateException(
                "You cannot remove the Atom object for another context"
            )
        thread = Local.instance()
        thread.atom = None

    def after(self, callbacks:List[Callable]):
        """Add callback hooks after the `successful` execution of this batch"""
        if callbacks and isinstance(callbacks, list):
            self.callbacks.extend(callbacks)

    def failure(self, errbacks:List[Callable]):
        if errbacks and isinstance(errbacks, list):
            self.errbacks.extend(errbacks)

    def __enter__(self):
        """Changes the current Thread Local Transaction to this object"""
        atom = self.get()
        if atom and atom != self:
            raise IllegalStateException(
                "You cannot have more than one active Atom object at once"
            )
        if self.run:
            raise IllegalStateException("You cannot enter a transaction that has already been run")
        self.set()
        return self

    def __exit__(self, *arguments, **kwds):
        """Execute the Transaction upon exit"""
        self.unset()
        if not self.run:
            self.commit()
    
    def commit(self):
        """Execute the Transaction"""
        try:
            if not self.open:
                raise IllegalStateException("Your transaction is not open")
            self.transaction.execute()
            self.open = False
        except Exception as e:
            raise e
        finally:
            self.run = True
        