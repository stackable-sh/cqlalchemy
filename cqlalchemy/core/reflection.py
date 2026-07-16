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

"""
Allows you to dynamically build Models, Tables and Keyspaces from existing
Keyspaces in C* using reflection.
"""

from typing import Type

from cqlalchemy.core.models import Define, UUID, TimeUUID, CqlProperty, Entity
from cqlalchemy.core.commons import (
    String, 
    Text,  
    Integer, 
    Blob, 
    Boolean, 
    Decimal, 
    Float, 
    Duration, 
    IP, 
    Time, 
    Date, 
    DateTime,
    List,
    Map, 
    Tuple,
    Set
)


__all__ = ["Image"]



# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Image

# The Image class is a convenience function for working with existing/legacy data/tables in C*.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def Image(
        name: str,
        keyspace: str = None,
        columns: dict[str, CqlProperty] = {},
        exclude: list[str] = [],
    ) -> Type[Entity]:
    """Creates a dynamic table that mirrors the table in C* using reflection"""
    pass



def reflect(keyspace: str, table: str) -> dict[str, Type["CqlProperty"]]:
    """Generates a dictionary of CqlProperties for a given keyspace and table"""
    return {}


__collections__ = {
    "list" : List, 
    "map" : Map,
    "set" : Set, 
    "tuple" : Tuple
}

__mapping__ = {
    "ascii" : Text,
    "bigint" : Integer,
    "varint" : Integer,
    "varchar" : String,
    "blob" : Blob,
    "boolean" : Boolean,
    "counter" : Integer,
    "decimal" : Decimal,
    "double" : Float,
    "duration" : Duration,
    "float" : Float,
    "inet" : IP,
    "int" : Integer,
    "smallint" : Integer,
    "text" : Text,
    "time" : Time,
    "date" : Date,
    "timestamp" : DateTime,
    "timeuuid" : TimeUUID,
    "tinyint" : Integer,
    "uuid" : UUID
}