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
Multi-Partition Batch Detection

Detects when a list of CQL DML statements will target multiple partitions,
enabling automatic escalation (upgrade) from a BATCH to an accord transaction (which is cheaper)
than a multi partition batch, or a (downgrade) to an unlogged batch (which is faster)
when all the updates are on a single partition.

Cassandra 5+ ships with Accord, which provides cheaper multi-partition atomic transactions.
This module provides the detection algorithm that enables cqlalchemy to automatically upgrade
and downgrade Batch transactions when appropriate.
"""

import re
from typing import List, Optional, Set
from dataclasses import dataclass

__all__ = [
    "is_multi_partition",
    "is_single_partition",
    "detect_single_partition",
    "detect_multi_partition",
    "can_upgrade",
    "can_upgrade_queries",
]


@dataclass(frozen=True)
class PartitionFingerprint:
    """
    Uniquely identifies the target partition of a CQL DML statement.

    A fingerprint consists of the table name and a frozenset of
    (column_name, value) pairs for the partition key columns. Two DML
    statements target the same partition if and only if their fingerprints
    are equal.
    """

    table: str
    partition: frozenset  # frozenset of (column_name, value_str) tuples

    def __repr__(self):
        pairs = ", ".join(f"{k}={v}" for k, v in sorted(self.partition))
        return f"<PartitionFingerprint(table='{self.table}', {pairs})>"


# ──────────────────────────────────────────────────────────────────────
# Structural Detection (Primary)
#
# Uses the Entity/Pointer objects already tracked by Batch.objects to
# extract partition key values directly from the Python object graph.
# This is zero-overhead and doesn't require any string parsing.
# ──────────────────────────────────────────────────────────────────────


def detect_multi_partition(objects) -> bool:
    """
    Detect multi-partition batches using the entity/pointer objects
    that are tracked by the Batch.

    This is the primary detection method. It inspects the `objects`
    tracked by a Batch (a WeakSet of Entity/Pointer instances) to determine
    whether they target more than one partition.

    Args:
        objects: An iterable of Entity and/or Pointer instances.

    Returns:
        True if the objects target more than one distinct partition.
    """
    from cqlalchemy.core.models import Entity, Pointer, Key

    seen: Set[PartitionFingerprint] = set()
    for obj in objects:
        fp = _fingerprint_from_object(obj)
        if fp is not None:
            seen.add(fp)
            if len(seen) > 1:
                return True  # Early exit
    return False


def detect_single_partition(objects) -> bool:
    """Checks if we are dealing with a single partition"""
    return not detect_multi_partition(objects)


def _fingerprint_from_object(obj) -> Optional[PartitionFingerprint]:
    """
    Extract a PartitionFingerprint from an Entity or Pointer instance.

    For Entity objects, we read partition key values directly from the
    instance attributes. For Pointer objects, we read them from the
    Pointer's parts dict.
    """
    from cqlalchemy.core.models import Entity, Pointer, Key

    if isinstance(obj, Entity):
        key = Key.create(obj.__class__)
        partition = []
        for name in key.partition:
            value = getattr(obj, name, None)
            # Normalize to string for consistent comparison
            partition.append((name, str(value)))
        return PartitionFingerprint(
            table=obj.table(),
            partition=frozenset(partition),
        )
    elif isinstance(obj, Pointer):
        key = Key.create(obj.kind)
        partition = []
        for name in key.partition:
            value = obj.parts.get(name, None)
            partition.append((name, str(value)))
        return PartitionFingerprint(
            table=obj.table,
            partition=frozenset(partition),
        )
    return None


# ──────────────────────────────────────────────────────────────────────
# String-Parsing Detection (Fallback)
#
# Regex-based extraction from CQL query strings. Used as a fallback
# when raw string queries are added to a Batch via batch.add("...").
# This is sound because cqlalchemy generates all CQL strings itself
# via predictable template formatting.
# ──────────────────────────────────────────────────────────────────────
# Patterns for extracting table names from DML queries


_INSERT_TABLE_RE = re.compile(r"INSERT\s+INTO\s+(\w+)\s*\(", re.IGNORECASE)
_UPDATE_TABLE_RE = re.compile(r"UPDATE\s+(\w+)\s", re.IGNORECASE)
_DELETE_TABLE_RE = re.compile(
    r"DELETE\s+.*?\s+FROM\s+(\w+)\s", re.IGNORECASE | re.DOTALL
)
# Fallback for "DELETE FROM table WHERE ..." (no column list)
_DELETE_TABLE_SIMPLE_RE = re.compile(r"DELETE\s+FROM\s+(\w+)\s", re.IGNORECASE)
# Pattern for extracting column-value pairs from INSERT
_INSERT_COLS_RE = re.compile(
    r"INSERT\s+INTO\s+\w+\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
    re.IGNORECASE,
)
# Pattern for extracting WHERE clause key=value pairs
_WHERE_PAIR_RE = re.compile(r"(\w+)\s*=\s*([^,\s;]+(?:\s+AND\s+)?)", re.IGNORECASE)
# Full WHERE clause extraction
_WHERE_CLAUSE_RE = re.compile(
    r"WHERE\s+(.+?)(?:\s*;|\s*IF\s|\s*$)", re.IGNORECASE | re.DOTALL
)


def extract_partition_fingerprint(query: str) -> Optional[PartitionFingerprint]:
    """
    Parse a CQL DML query string and extract a PartitionFingerprint.

    Supports INSERT, UPDATE, and DELETE queries generated by cqlalchemy.
    Returns None if the query cannot be parsed.

    Args:
        query: A CQL DML query string (INSERT, UPDATE, or DELETE).

    Returns:
        A PartitionFingerprint, or None if the query cannot be parsed.
    """
    from cqlalchemy.connection.table import Schema
    from cqlalchemy.core.models import Key

    query = query.strip()
    if not query:
        return None
    query_type = query.split()[0].upper()
    if query_type == "INSERT":
        return _fingerprint_from_insert_(query)
    elif query_type == "UPDATE":
        return _fingerprint_from_update_(query)
    elif query_type == "DELETE":
        return _fingerprint_from_delete_(query)
    return None


def _fingerprint_from_insert_(query: str) -> Optional[PartitionFingerprint]:
    """Extract a fingerprint from an INSERT query."""
    from cqlalchemy.connection.table import Schema
    from cqlalchemy.core.models import Key

    # Extract the table name
    match = _INSERT_TABLE_RE.search(query)
    if not match:
        return None
    table = match.group(1).lower()
    # Extract columns and values
    match = _INSERT_COLS_RE.search(query)
    if not match:
        return None
    columns = [c.strip() for c in match.group(1).split(",")]
    values = _split_values_(match.group(2))
    if len(columns) != len(values):
        return None  # Malformed query
    # Look up the entity to find its partition keys
    entity = Schema.get(table)
    if not entity:
        # If we can't look up the entity, use the table name + all WHERE pairs
        # as a best-effort fingerprint
        return PartitionFingerprint(
            table=table,
            partition=frozenset(zip(columns, values)),
        )
    key = Key.create(entity)
    partition_pairs = []
    for col, val in zip(columns, values):
        if col.strip() in key.partition:
            partition_pairs.append((col.strip(), val.strip()))
    return PartitionFingerprint(
        table=table,
        partition=frozenset(partition_pairs),
    )


def _fingerprint_from_update_(query: str) -> Optional[PartitionFingerprint]:
    """Extract a fingerprint from an UPDATE query."""
    from cqlalchemy.connection.table import Schema
    from cqlalchemy.core.models import Key

    match = _UPDATE_TABLE_RE.search(query)
    if not match:
        return None
    table = match.group(1).lower()
    return _fingerprint_from_where_clause_(query, table)


def _fingerprint_from_delete_(query: str) -> Optional[PartitionFingerprint]:
    """Extract a fingerprint from a DELETE query."""
    from cqlalchemy.connection.table import Schema
    from cqlalchemy.core.models import Key

    match = _DELETE_TABLE_RE.search(query)
    if not match:
        match = _DELETE_TABLE_SIMPLE_RE.search(query)
    if not match:
        return None
    table = match.group(1).lower()
    return _fingerprint_from_where_clause_(query, table)


def _fingerprint_from_where_clause_(
    query: str, table: str
) -> Optional[PartitionFingerprint]:
    """
    Extract a partition fingerprint from the WHERE clause of an
    UPDATE or DELETE query.
    """
    from cqlalchemy.connection.table import Schema
    from cqlalchemy.core.models import Key

    where_match = _WHERE_CLAUSE_RE.search(query)
    if not where_match:
        return None
    where_text = where_match.group(1)
    # Split on AND to get individual conditions
    conditions = re.split(r"\s+AND\s+", where_text, flags=re.IGNORECASE)
    where_pairs = []
    for condition in conditions:
        condition = condition.strip()
        # Match simple "name = value" or "name=value" patterns
        eq_match = re.match(r"(\w+)\s*=\s*(.+)", condition)
        if eq_match:
            col = eq_match.group(1).strip()
            val = eq_match.group(2).strip().rstrip(";")
            where_pairs.append((col, val))
    entity = Schema.get(table)
    if not entity:
        # Best-effort: use all WHERE pairs
        return PartitionFingerprint(
            table=table,
            partition=frozenset(where_pairs),
        )
    key = Key.create(entity)
    partition_pairs = [(col, val) for col, val in where_pairs if col in key.partition]
    return PartitionFingerprint(
        table=table,
        partition=frozenset(partition_pairs),
    )


def _split_values_(values_str: str) -> List[str]:
    """
    Split a CQL VALUES clause into individual value strings,
    respecting quoted strings, nested collections, and function calls.

    Example:
        "'hello', 123, {'a': 1}" -> ["'hello'", "123", "{'a': 1}"]
    """
    values = []
    current = []
    depth = 0
    in_quote = False
    escape = False
    for char in values_str:
        if escape:
            current.append(char)
            escape = False
            continue
        if char == "\\":
            current.append(char)
            escape = True
            continue
        if char == "'" and not in_quote:
            in_quote = True
            current.append(char)
            continue
        if char == "'" and in_quote:
            # CQL uses '' for escaping quotes inside strings
            in_quote = False
            current.append(char)
            continue
        if in_quote:
            current.append(char)
            continue
        if char in ("{", "[", "("):
            depth += 1
            current.append(char)
            continue
        if char in ("}", "]", ")"):
            depth -= 1
            current.append(char)
            continue
        if char == "," and depth == 0:
            values.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        values.append("".join(current).strip())
    return values


def is_multi_partition(queries: List[str]) -> bool:
    """
    Determine if a list of CQL DML query strings target multiple partitions.

    This is the string-parsing based detection, used as a fallback when
    structural detection (via `detect_multi_partition`) is not available.

    Args:
        queries: A list of CQL DML query strings.

    Returns:
        True if the queries target more than one distinct partition.
    """
    if len(queries) <= 1:
        return False
    fingerprints: Set[PartitionFingerprint] = set()
    for query in queries:
        text = query if isinstance(query, str) else str(query)
        fp = extract_partition_fingerprint(text)
        if fp is not None:
            fingerprints.add(fp)
            if len(fingerprints) > 1:
                return True  # Early exit
    return False


def is_single_partition(queries: List[str]) -> bool:
    """
    Determine if a list of CQL DML query strings target multiple partitions.

    This is the string-parsing based detection, used as a fallback when
    structural detection (via `detect_multi_partition`) is not available.

    Args:
        queries: A list of CQL DML query strings.

    Returns:
        True if the queries target more than one distinct partition.
    """
    return not is_multi_partition(queries)


def can_upgrade(objects) -> bool:
    """
    Check whether all entities participating in a batch support Accord
    transactions and can therefore be escalated.

    Args:
        objects: An iterable of Entity and/or Pointer instances.

    Returns:
        True if all entities support Accord (`accord=True`).
    """
    from cqlalchemy.core.models import Entity, Pointer, options

    for obj in objects:
        if isinstance(obj, Entity):
            entity_cls = obj.__class__
        elif isinstance(obj, Pointer):
            entity_cls = obj.kind
        else:
            continue
        accord = options(entity_cls, "accord", False)
        if not accord:
            return False
    return True


def can_upgrade_queries(queries: List[str]) -> bool:
    """
    Check whether all tables referenced by a list of CQL query strings
    support Accord transactions.

    Args:
        queries: A list of CQL DML query strings.

    Returns:
        True if all referenced entities support Accord.
    """
    from cqlalchemy.connection.table import Schema
    from cqlalchemy.core.models import options

    for query in queries:
        text = query if isinstance(query, str) else str(query)
        fp = extract_partition_fingerprint(text)
        if fp is not None:
            entity = Schema.get(fp.table)
            if entity:
                accord = options(entity, "accord", False)
                if not accord:
                    return False
    return True
