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


###################################################################################
# This environment was automatically generated, please edit to suit your usecase. #
###################################################################################

from typing import List
from pathlib import Path

import cqlalchemy
import cqlalchemy.options
from cqlalchemy.core.models import Model
from cqlalchemy.core.commons import String, Set
from cqlalchemy.revisions import Project


class Book(Model):
    name = String(index=True, required=True)
    publisher = String(index=True, required=True)
    editions = Set(String)


class Environment(Project):

    def connect(self):
        """Setup the environment including configuring C* access"""
        try:
            cqlalchemy.configure(
                keyspace="Test",
                servers=[
                    "localhost",
                ],
                debug=True,
                verbose=True,
            )
        except Exception as e:
            raise e

    def entities(self):
        """Help the migration subsystem find your entity classes"""
        entities = [
            Book,
        ]
        return entities


current = Path(__file__).resolve()
project = Environment(root=current.parent)
