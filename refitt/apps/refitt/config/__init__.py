# Copyright REFITT Team 2019. All rights reserved.
#
# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Manage runtime configuration."""

# standard libs
import sys

# internal libs
from ....core.logging import Logger
from ....core.exceptions import CompletedCommand
from ....__meta__ import __appname__, __copyright__, __developer__, __contact__, __website__

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface, ArgumentError

# commands
from .get import Get
from .set import Set
from .edit import Edit


COMMANDS = {
    'get': Get,
    'set': Set,
    'edit': Edit,
}


PROGRAM = f'{__appname__} config'
PADDING = ' ' * len(PROGRAM)

USAGE = f"""\
usage: {PROGRAM} <command> [<args>...]
       {PADDING} [--help]

{__doc__}\
"""

EPILOG = f"""\
Documentation and issue tracking at:
{__website__}

Copyright {__copyright__}
{__developer__} {__contact__}.\
"""

HELP = f"""\
{USAGE}

commands:
get                      {Get.__doc__}
set                      {Set.__doc__}
edit                     {Edit.__doc__}

options:
-h, --help               Show this message and exit.

files:
/etc/refitt.toml         System configuration.
~/.refitt/config.toml    User configuration.
./.refitt/config.toml    Local configuration.

Use the -h/--help flag with the above groups/commands to
learn more about their usage.

{EPILOG}\
"""


# initialize module level logger
log = Logger.with_name('.'.join(PROGRAM.split()))


class ConfigGroup(Application):
    """Manage runtime configuration."""

    interface = Interface(PROGRAM, USAGE, HELP)

    command: str = None
    interface.add_argument('command')

    exceptions = {
        CompletedCommand: (lambda exc: int(exc.args[0])),
    }

    def run(self) -> None:
        """Show usage/help/version or defer to command."""

        if self.command in COMMANDS:
            status = COMMANDS[self.command].main(sys.argv[3:])
            raise CompletedCommand(status)
        else:
            raise ArgumentError(f'"{self.command}" is not a command.')
