# Copyright 2026 Iroiso Ikpokonte
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__all__ = [
    "BaseException",
    "BadValueError",
    "IncompleteModelError",
    "InvalidatedModelError",
    "IllegalStateException",
    "CqlQueryException",
    "ConnectionError",
    "IsolatedStaticFieldException",
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


class InvalidatedModelError(BaseException):
    """Raised by Model, when you attempt to use it after invalidation"""

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
