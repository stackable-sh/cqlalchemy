__all__ = [
    "BaseException", 
    "BadValueError", 
    "IncompleteModelError", 
    "IllegalStateException", 
    "CqlQueryException",
    "ConnectionError",
    "IsolatedStaticFieldException"
]

class BaseException(Exception):
    """Base exception for all CQLAlchemy exceptions."""
    pass 

class BadValueError(BaseException):
    """Raised by descriptors to indicate an invalid value has been provided."""
    pass 

class IncompleteModelError(BaseException):
    """Raised by Model, when a required field has not been provided."""
    pass

class IllegalStateException(BaseException):
    """General Exception to signal internal state inconsistency"""
    pass

class CqlQueryException(BaseException):
    """An Error that signifies that something bad happened during a CqlQuery"""
    pass

class ConnectionError(BaseException):
    """Base class for all Connection related exceptions"""
    pass

class IsolatedStaticFieldException(BaseException):
    """Raised when trying to save an instance with an isolated static field."""
    pass
    