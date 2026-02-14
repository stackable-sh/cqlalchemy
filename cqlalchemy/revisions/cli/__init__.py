
import os
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Union
from pathlib import Path

import fire 

from cqlalchemy.options import keyspace
from cqlalchemy.time import minutes
from cqlalchemy.core.models import options
from cqlalchemy.connection.table import Schema, Metadata
from cqlalchemy.revisions import Project, Revision, State
from cqlalchemy.revisions.templates import new_empty_file, new_project


from cqlalchemy.revisions import load
from cqlalchemy.revisions.cli.commands import (
    Initialize, 
    New, 
    Reset, 
    Stamp, 
    Head, 
    History, 
    Migrate,
    Sync
)



"""
ActionContext
Facade which allows you to execute commands from the terminal
"""

class ActionContext(object):
    """Terminal operations facade"""
        
    def migrate(self, stop:str=None):
        """Sequentially applies all fresh migrations until we get to @stop"""
        project = os.path.join(os.getcwd(), "revisions")
        if os.path.exists(project):
            env = load(project)
            command = Migrate(stop=stop)
            command.execute(env)
        else:
            print("There doesn't seem to be a Revision Project in this directory")

    def history(self):
        """Prints the status of all migrations from C*"""
        project = os.path.join(os.getcwd(), "revisions")
        if os.path.exists(project):
            env = load(project)
            command = History()
            command.execute(env)
        else:
            print("There doesn't seem to be a Revision Project in this directory")

    def head(self):
        """Prints information about the current HEAD of the migration"""
        project = os.path.join(os.getcwd(), "revisions")
        if os.path.exists(project):
            env = load(project)
            command = Head()
            command.execute(env)
        else:
            print("There doesn't seem to be a Revision Project in this directory")

    def stamp(self, revision:str):
        """Manually marks a particular migration as successful in C*"""
        project = os.path.join(os.getcwd(), "revisions")
        if os.path.exists(project):
            env = load(project)
            command = Stamp(revision=revision)
            command.execute(env)
        else:
            print("There doesn't seem to be a Revision Project in this directory")

    def reset(self):
        """Removes the entire keyspace from C*, so that you can start afresh"""
        project = os.path.join(os.getcwd(), "revisions")
        if os.path.exists(project):
            env = load(project)
            command = Reset()
            command.execute(env)
        else:
            print("There doesn't seem to be a Revision Project in this directory")

    def new(self, message:str="", auto:bool=False, reverse:str=None):
        """Generates a new C* schema revision"""
        project = os.path.join(os.getcwd(), "revisions")
        if os.path.exists(project):
            env = load(project)
            command = New(messsage=message, discover=auto, reverse=reverse)
            command.execute(env)
        else:
            print("There doesn't seem to be a Revision Project in this directory")

    def sync(self, dir:str=None):
        """Syncs your model with your database"""
        if dir:
            project = load(dir)
        else:
            dir = os.path.join(os.getcwd(), "revisions")
            project = load(dir)
        if project.valid():
            command = Sync()
            command.execute(project=project)
        else:
            print(f"Invalid Revision Project: {dir}")
    
    def init(self, dir:Union[str, Path]=None):
        """Creates a new migration project"""
        if dir:
            project = os.path.join(dir, "revisions")
        else:
            project = os.path.join(os.getcwd(), "revisions")
        if os.path.exists(project):
            project = Project(project)
            if project.valid():
                print("Another Revision Project already exists in this directory")
        else:
            project = Project(project)
            command = Initialize()
            command.execute(project)


"""
run 

Entry point for the script. 
"""

def run():
    """Runs the migration script"""
    fire.Fire(ActionContext)