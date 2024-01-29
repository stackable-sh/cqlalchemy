import os
import fire 

from cqlalchemy.migrate import load, EnvironmentContext
from cqlalchemy.migrate.commands import (
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

    def sync(self):
        """Syncs your model with your database"""
        command = Sync()
        command.execute(env=None)
    
    def init(self, description:str=""):
        """Creates a new migration project"""
        print("Initializing Project.")
        project = os.path.join(os.getcwd(), "revisions")
        if os.path.exists(project):
            print("Another Revision Project already seems to exist in this directory")
        else:
            env = EnvironmentContext(project)
            command = Initialize(description=description)
            command.execute(env)


"""
run 

Entry point for the script. 
"""

def run():
    """Runs the migration script"""
    fire.Fire(ActionContext)