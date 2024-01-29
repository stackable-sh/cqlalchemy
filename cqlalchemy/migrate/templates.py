


new_migration = """
###################################################################################
# This migration was automatically generated, please edit to suit your usecase.   #
###################################################################################

'''
Name: {name}
Revision: {revision}
Date: {timestamp}
Description: {description}
'''

from cqlalchemy.time import minutes
from cqlalchemy.migrate import Migration, Op


class DatabaseRevision(Migration, idempotent=True, retry=5, duration=minutes(5)):
    '''{description}'''

    def prepare(self):
        '''Initialise & perform preparatory work here (that does not involve actual data/schema migration)'''
        print('(1) Preparing for migration')

    def before(self):
        '''Perform any data migrations required before the schema change'''
        print('(2) Perform Any `Pre-Schema Change` Data Migration.')

    def actions(self) -> List[Operation]:
        '''Declarative Schema Migration Ops here'''
        print('(3) Generate `Schema Change` Operations Here.')
        ops = {operations}
        return ops

    def after(self):
        '''Perform any data migrations, post schema change'''
        print('(4) Perform `Post Schema Change` Data Migration Here.')
    
    def shutdown(self):
        '''Perform any clean up actions here'''
        print('(5) Perform clean up actions, and release any shared resources here.')


migration = DatabaseRevision(revision='{revision}', labels={labels})
"""


new_empty_file = """
###################################################################################
# This environment was automatically generated, please edit to suit your usecase. #
###################################################################################
"""


new_env = """
###################################################################################
# This environment was automatically generated, please edit to suit your usecase. #
###################################################################################

'''
Name: {name}
Revision: {revision}
Date: {timestamp}
Description: {description}
'''

from typing import List

import cqlalchemy
from cqlalchemy.migrate import EnvironmentContext


class Environment(EnvironmentContext):
    '''{description}'''

    def configure(self):
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
 
    def discover(self):
        '''Help the migration subsystem find your entity classes'''
        entities = super().discover()
        entities.extend([
            # Add your entity classes here.
        ])
        return entities

env = Environment(root='revisions')
"""
