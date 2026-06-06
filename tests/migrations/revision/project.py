
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
        '''Setup the environment including configuring C* access'''
        try:
            cqlalchemy.configure(
                keyspace="Test", 
                servers=["localhost",],
                debug=False, 
                verbose=False,
            )
        except Exception as e:
            raise e

    def entities(self):
        '''Help the migration subsystem find your entity classes'''
        entities = [
            Book,
        ]
        return entities

current = Path(__file__).resolve()
project = Environment(root=current.parent)

