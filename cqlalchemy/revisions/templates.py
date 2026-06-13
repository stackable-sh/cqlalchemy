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

# Templates for revision project generation

new_migration = """
###################################################################################
# This migration was automatically generated, please edit to suit your usecase.   #
###################################################################################

from pathlib import Path 
from typing import List, Union

from cqlalchemy.time import minutes
from cqlalchemy.revisions.operations import *
from cqlalchemy.revisions import Migration


class DatabaseMigration(Migration, idempotent=True, retry=5, duration=minutes(5)):
    '''Briefly describe the purpose of this migration'''

    def before(self):
        '''(1) Perform any data migrations required before the schema change'''
        pass

    def actions(self) -> Union[Operation, List["Operation"]]:
        '''(2) Write Declarative Schema Migration Ops here'''
        ops = {operations}
        return ops

    def after(self):
        '''(3) Perform any data migrations, post schema change here'''
        pass

current = Path(__file__).resolve()
revision = DatabaseMigration(
    revision='{revision}', 
    message='{message}', 
    path=current
)
"""


new_empty_file = """
###################################################################################
# This environment was automatically generated, please edit to suit your usecase. #
###################################################################################
"""


new_project = """
###################################################################################
# This environment was automatically generated, please edit to suit your usecase. #
###################################################################################

from typing import List
from pathlib import Path

import cqlalchemy
from cqlalchemy.revisions import Project


class Environment(Project):

    def connect(self):
        '''Setup the environment including configuring C* access'''
        try:
            # Please update the connection configuration here. 
            cqlalchemy.configure(
                keyspace="Test", 
                servers=["localhost",],
                debug=True, 
                verbose=True,
            )
        except Exception as e:
            raise e

    def entities(self):
        '''Help the migration subsystem find your entity classes'''
        entities = [
            # Add your entity classes here.
        ]
        return entities

current = Path(__file__).resolve()
project = Environment(root=current.parent)
"""
