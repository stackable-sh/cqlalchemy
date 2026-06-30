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


import os
from typing import Union
from pathlib import Path

import fire
from rich import print
from rich.prompt import Confirm

from cqlalchemy.revisions import Project, MigrationException, State
from cqlalchemy.revisions.cli.commands import (
    Initialize,
    New,
    Reset,
    Stamp,
    Head,
    History,
    Migrate,
    Sync,
    Baseline,
    RevisionChecksumException,
    ConcurrentMigrationException,
    MigrationCompletedException,
    StopMigrationException,
    RevisionAppliedException,
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

    def __init__(self, directory: Union[str, Path]):
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
            print(
                f"[bold green]Loaded Revision Project at: {self.directory}[/bold green]"
            )
        except MigrationException as e:
            pass

    def prepare(self):
        """Prepare the Revision Project for use"""
        if self.connected:
            return
        self.project.connect()
        self.project.setup()
        self.connected = True

    def init(self, name: str = "revision"):
        """Creates a new migration project"""
        if name:
            path = os.path.join(self.directory, name)
        else:
            path = os.path.join(self.directory, "revision")
        if os.path.exists(path):
            project = Project(path)
            if project.valid():
                print(
                    "[bold red]Another Revision Project already exists in this directory[/bold red]"
                )
                self.project = project
                self.prepare()
                print("")
                print(
                    f"[bold green]Loaded Revision Project at: {self.directory}[/bold green]"
                )
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

    def new(self, message: str, create: bool = True):
        """Generates a new C* schema revision"""
        self.prepare()
        command = New(message=message, create=create)
        command.execute(project=self.project)

    def migrate(self, start: str = None, stop: str = None, **keywords):
        """Sequentially applies all migrations until we get to @stop"""
        self.prepare()

        suppress_exceptions = keywords.get("suppress_exceptions", True)
        confirm = keywords.get("confirm", False)
        checksums, reruns = set(), set()
        command = Migrate(start=start, stop=stop)

        while True:
            try:
                command.execute(
                    project=self.project, allowed_checksums=checksums, rerun=reruns
                )
            except RevisionChecksumException as e:
                if not suppress_exceptions:
                    raise e
                print(
                    "[bold cyan]Your migration script seems to have changed since the last run[/bold cyan]"
                )
                if not confirm:
                    approval = Confirm.ask(
                        "[bold cyan]Do you want to run it again?[/bold cyan]"
                    )
                    if not approval:
                        print("[bold red]Stopping the migration.[/bold red]")
                        break
                print("[bold green]Continuing with the migration script.[/bold green]")
                checksums.add(e.checksum)
            except ConcurrentMigrationException as e:
                print(
                    "[bold red]Another CQLAlchemy migration seems to be already running against your C* cluster[bold red]"
                )
                print("[bold red]Stopping this migration[/bold red]")
                if not suppress_exceptions:
                    raise e
            except RevisionAppliedException as e:
                if not suppress_exceptions:
                    raise e
                print(
                    f"[bold cyan]Migration {e.revision} has already been applied to the database[/bold cyan]"
                )
                if not confirm:
                    approval = Confirm.ask(
                        "[bold red]Do you want to run it again?[/bold red]"
                    )
                    if not approval:
                        print("[bold red]Stopping the migration.[/bold red]")
                        break
                print("\n")
                print("[bold green]Continuing with the migration script.[/bold green]")
                reruns.add(e.revision)
            except StopMigrationException as e:
                print(
                    f"[bold yellow]Migration stopped sucessfully at: {e.migration}[/bold yellow]"
                )
                break
            except MigrationCompletedException as e:
                if command.succeeded:
                    print("[bold green]Migration completed successfully![/bold green]")
                else:
                    print(
                        "[bold red]Unfortunately, the migration did not complete successfullly.[/bold red]"
                    )
                break
        command.display()

    def stamp(self, revision: str, state=State.APPLIED):
        """Manually marks a particular migration as successful in C*"""
        self.prepare()
        command = Stamp(revision=revision, state=state)
        command.execute(self.project)

    def head(self, **keywords):
        """Prints information about the current HEAD of the migration"""
        self.prepare()
        suppress_result = keywords.get("suppress_result", True)
        command = Head()
        result = command.execute(self.project, suppress_result=suppress_result)
        if not suppress_result:
            return result

    def history(self, **keywords):
        """Prints the status of all migrations from C*"""
        self.prepare()
        suppress_result = keywords.get("suppress_result", True)
        command = History()
        result = command.execute(self.project, suppress_result=suppress_result)
        if not suppress_result:
            return result

    def reset(self, to=None, **keywords):
        """Removes the entire keyspace from C*, so that you can start afresh"""
        self.prepare()

        suppress_result = keywords.get("suppress_result", False)
        suppress_exceptions = keywords.get("suppress_exceptions", True)
        confirm = keywords.get("confirm", False)
        result = None
        command = Reset()

        if to:
            result = command.execute(
                self.project, confirm=confirm, suppress_result=False
            )
            if result:
                self.project.setup(force=True)
                self.migrate(
                    stop=to, suppress_exceptions=suppress_exceptions, confirm=confirm
                )
                result = True  # If nothing went wrong, then we return True
        else:
            result = command.execute(
                self.project, confirm=confirm, suppress_result=False
            )
        if not suppress_result:
            return result

    def baseline(self, to=None, **keywords):
        """Marks all existing migrations as already applied"""
        self.prepare()
        suppress_result = keywords.get("suppress_result", False)
        command = Baseline(to=to)
        result = command.execute(self.project, suppress_result=suppress_result)
        command.display()
        if not suppress_result:
            return result


"""
run 

Entry point for the script. 
"""


def run():
    """Runs the migration script"""
    fire.Fire(ActionContext)
