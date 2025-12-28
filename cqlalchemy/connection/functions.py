"""Scalar & Aggregate CQL functions to enrich queries"""

from cqlalchemy.core.builtins import assertNonNull, assertType
from cqlalchemy.connection.cql.expr import Functor, Predicate, Column

__all__ = [
    "row",
    "when",
    "r",
]




def row(name:str) -> Column:
    """A query helper for row matching"""
    assertNonNull(name, "You must provide a non-null str object as paramater")
    assertType(name, str, "You must provide a str object as paramater")
    return Column(name)


"""
when

Syntatic sugar for creating and using cql expressions for LWT and Conditional Updates. 
You can use `when` whenever a Predicate is required by cqlalchemy.

```python
class Author(Model):
    name = String(index=True)
    age = Integer(index=True)
    bio = String(index=True, required=True)

author = Author.create(
    name="Walter Isaacson", 
    bio="I write autobiographies", 
    age=20
)
assert author.name == "Walter Isaacson"

author = Author.upsert(
    name="Charles Dickens", 
    condition=when(name="Walter Isaacson")
)
assert author.name == "Charles Dickens"
assert Author.objects.count() == 1

# If you want deeper conditions, go for them using the row matching syntax. 

author = (Author
    .upsert(
        name="Charles Dickens", 
        condition=when(
            row("name") == "Walter Isaacson",
            row("age") >= 18    
        )
    )
    .get()
)
assert author.name == "Charles Dickens"
assert Author.objects.count() == 1

# Or even:

author = Author.upsert(
    name="Charles Dickens", 
    condition=when(
        r("name") == "Walter Isaacson",
        r("age") >= 18    
    )
)
assert author.name == "Charles Dickens"
assert Author.objects.count() == 1
```
"""


def when(*arguments, **keywords):
    """Shortcute for creating Predicate objects"""
    return Predicate(*arguments, **keywords)

# Shortcut for a `row` function
r = row