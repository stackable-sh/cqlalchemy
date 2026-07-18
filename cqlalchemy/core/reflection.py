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

from cqlalchemy.connection.table import Schema, Metadata
from cqlalchemy.options import keyspace as root
from cqlalchemy.core.models import Define, UUID, TimeUUID, CqlProperty, Entity, Model
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
    Set,
)

__all__ = ["Image"]


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
# Image

# The Image class is a convenience function for working with existing/legacy data/tables in C*.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def Image(
    table: str,
    base: Type[Entity] = Model,
    metadata: Metadata = None,
    keyspace: str = None,
    batch: bool = True,
    expire: int = 0,
    columns: dict[str, CqlProperty] = {},
    exclude: list[str] = [],
) -> Type[Entity]:
    """Creates a dynamic table that mirrors the table in C* using reflection"""
    keyspace = root() if not keyspace else keyspace.lower()
    if not table:
        raise ValueError("Provide a valid `table` name to proceed")

    table = table.lower()
    accord = Schema.allows_accord(keyspace, table)
    properties = reflect(keyspace, table, metadata)
    for name in exclude:
        if name in properties:
            del properties[name]
    for name, column in columns.items():
        properties[name] = column
    cls = Define(
        name=table.title(),
        parent=base,
        keyspace=keyspace,
        version=False,
        batch=batch,
        accord=accord,
        expire=expire,
        image=True,
        columns=properties,
    )
    cls()  # Create a throwaway instance to initialize Model persistence machinery
    return cls


def reflect(
    keyspace: str, table: str, metadata: Metadata = None
) -> dict[str, Type["CqlProperty"]]:
    """Generates a dict of properties for the table using driver metadata"""
    if not (keyspace and table):
        raise ValueError("Provide a valid `keyspace` and `table`")

    output = {}
    metadata = Metadata.get(keyspace) if not metadata else metadata
    primary = metadata.keys(table, partition=True, cluster=False)[0]
    for name, column in metadata.columns(table).items():
        strip = ["<", ">", ",", " "]
        data_type = column["type"]
        results = []
        for char in data_type:
            if char not in strip:
                results.append(char)
            else:
                results.append(" ")
        results = "".join(results)
        results = results.split(" ")
        results = [result.strip() for result in results if result.strip()]
        if "frozen" in results:
            results.remove("frozen")
        base = results[0]
        if base in _collections_:
            match base:
                case "map":
                    first = _mapping_[results[1]]
                    second = _mapping_[results[2]]
                    static = metadata.static(table, name)
                    index = metadata.indexed(table, name)
                    prop = Map(first, second, static=static, index=index)
                case "list":
                    first = _mapping_[results[1]]
                    static = metadata.static(table, name)
                    index = metadata.indexed(table, name)
                    prop = List(first, static=static, index=index)
                case "set":
                    first = _mapping_[results[1]]
                    static = metadata.static(table, name)
                    index = metadata.indexed(table, name)
                    prop = Set(first, static=static, index=index)
                case "tuple":
                    others = [_mapping_[val] for val in results[1:]]
                    prop = Tuple(*others)
            output[name] = prop
        elif base in _mapping_:
            Property = _mapping_[base]
            if name == primary:
                keys = set(metadata.keys(table, cluster=False))
                keys.remove(primary)
                output[name] = Property(primary=True, composite=list(keys))
            else:
                index = metadata.indexed(table, name)
                static = metadata.static(table, name)
                key = name in metadata.keys(table)
                output[name] = Property(static=static, key=key, index=index)
    return output


_collections_ = {"list": List, "map": Map, "set": Set, "tuple": Tuple}

_mapping_ = {
    "ascii": Text,
    "bigint": Integer,
    "varint": Integer,
    "varchar": String,
    "blob": Blob,
    "boolean": Boolean,
    "counter": Integer,
    "decimal": Decimal,
    "double": Float,
    "duration": Duration,
    "float": Float,
    "inet": IP,
    "int": Integer,
    "smallint": Integer,
    "text": Text,
    "time": Time,
    "date": Date,
    "timestamp": DateTime,
    "timeuuid": TimeUUID,
    "tinyint": Integer,
    "uuid": UUID,
}
