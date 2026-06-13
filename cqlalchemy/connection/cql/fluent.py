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