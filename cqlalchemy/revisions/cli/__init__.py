
import os
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Union
from pathlib import Path

import fire 
from rich import print

from cqlalchemy.options import keyspace
from cqlalchemy.time import minutes
from cqlalchemy.core.models import options
from cqlalchemy.connection.table import Schema, Metadata
from cqlalchemy.revisions import Project, Revision, State, MigrationException
from cqlalchemy.revisions.templates import new_empty_file, new_project
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
    project: Project 
    directory: Union[str, Path]
    connected: bool

    def __init__(self, directory:Union[str, Path]):
        try:
            self.connected = False
            self.directory = directory
            if directory:
                project = Project.boot(directory)
            else:
                project = Project.boot(os.getcwd())
            self.project = project
            self.prepare()
            print("")
            print(f"[bold green]Loaded Revision Project at: {self.directory}[/bold green]")
        except MigrationException as e:
            pass 
    
    def prepare(self):
        """Prepare the Revision Project for use"""
        if self.connected:
            return 
        self.project.connect()
        self.project.setup()
        self.connected = True

    def init(self, name:str="revision"):
        """Creates a new migration project"""
        if name:
            path = os.path.join(self.directory, name)
        else:
            path = os.path.join(self.directory, "revision")
        if os.path.exists(path):
            project = Project(path)
            if project.valid():
                print("[bold red]Another Revision Project already exists in this directory[/bold red]")
                self.project = project
                self.prepare()
                print("")
                print(f"[bold green]Loaded Revision Project at: {self.directory}[/bold green]")
            else:
                raise ValueError(f"Invalid Revision Project at: {path}")
        else:
            self.project = Project(path)
            command = Initialize()
            command.execute(project=self.project)

    def sync(self):
        """Syncs your model with your database"""
        self.prepare()
        command = Sync()
        command.execute(project=self.project)
    
    def new(self, message:str, create:bool=True):
        """Generates a new C* schema revision"""
        self.prepare()
        command = New(message=message, create=create)
        command.execute(project=self.project)

    def migrate(self, start:str=None, stop:str=None):
        """Sequentially applies all fresh migrations until we get to @stop"""
        self.prepare()
        command = Migrate(start=start, stop=stop)
        command.execute(self.project)

    def history(self):
        """Prints the status of all migrations from C*"""
        self.prepare()
        command = History()
        command.execute(self.project)

    def head(self):
        """Prints information about the current HEAD of the migration"""
        self.prepare()
        command = Head()
        command.execute(self.project)

    def stamp(self, revision:str):
        """Manually marks a particular migration as successful in C*"""
        self.prepare()
        command = Stamp(revision=revision)
        command.execute(self.project)

    def reset(self):
        """Removes the entire keyspace from C*, so that you can start afresh"""
        self.prepare()
        command = Reset()
        command.execute(self.project)


"""
run 

Entry point for the script. 
"""

def run():
    """Runs the migration script"""
    fire.Fire(ActionContext)