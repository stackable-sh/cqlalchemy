# Templates for revision project generation

new_migration = """
###################################################################################
# This migration was automatically generated, please edit to suit your usecase.   #
###################################################################################
from typing import List, Union

from cqlalchemy.time import minutes
from cqlalchemy.revisions.operations import *
from cqlalchemy.revisions import Migration


class DatabaseRevision(Migration, idempotent=True, retry=5, duration=minutes(5)):
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


revision = DatabaseRevision(revision='{revision}', message='{message}')
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
