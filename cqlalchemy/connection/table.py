"""Facade for Table supporting implementations for Model, Expando, and Counter"""


"""
Schema:

"""
class Schema(object):
    """Handles Keyspace and Table operations in C*"""
    pass


"""
Table:

"""
class Table(object):
    """"Abstraction of a C* Table"""

    def truncate(self):
        """Deletes all the rows in this Table"""
        pass 

"""
ExpandoTable
Lower level facade for Expando.
"""
class ExpandoTable(Table):
    """Implementation proxy for Expando objects"""
    
    def __init__(self, kind):
        super().__init__()


class ModelTable(Table):
    """Implementation proxy for Model objects"""

    def __init__(self, kind):
        super().__init__()


class CounterTable(Table):
    """Implementation proxy for Counter objects"""
    
    def __init__(self, kind):
        super().__init__()

