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
        '''Perform any data migrations required before the schema change'''
        print('(1) Perform Any `Pre-Schema Change` Data Migration.')

    def actions(self) -> Union[Operation, List["Operation"]]:
        '''Declarative Schema Migration Ops here'''
        print('(2) Write `Schema Change` Operations Here.')
        ops = {operations}
        return ops

    def after(self):
        '''Perform any data migrations, post schema change'''
        print('(3) Perform `Post Schema Change` Data Migration Here.')


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
