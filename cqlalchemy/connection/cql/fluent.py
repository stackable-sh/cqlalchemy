from cqlalchemy.core.models import Entity
from cqlalchemy.connection.cql import (
    SelectQuery, UpdateQuery, DeleteQuery, InsertQuery,
)


"""
select:
fluent entry point for building SELECT queries from Models
"""
def select(entity: "Entity"):
    """Builds a SELECT query"""
    return SelectQuery(entity)


"""
update:
fluent entry point for building UPDATE queries from Models
"""
def update(entity: "Entity"):
    """Create an UPDATE query for an Entity"""
    return UpdateQuery(entity)


"""
delete:
fluent entry point for building DELETE queries from Models
"""
def delete(entity: "Entity"):
    """Create a DELETE query for an Entity"""
    return DeleteQuery(entity)


"""
insert:
fluent entry point for building INSERT queries from Models
"""
def insert(entity: "Entity"):
    """Create an INSERT query for an Entity"""
    return InsertQuery(entity)