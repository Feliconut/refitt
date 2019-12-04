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

"""Select data from REFITT's database."""

# standard libs
import os
import sys
import functools

# internal libs
from ... import database
from ...core.logging import logger
from ...__meta__ import (__appname__, __copyright__, __developer__,
                         __contact__, __website__)

# external libs
from cmdkit.app import Application
from cmdkit.cli import Interface
from tabulate import tabulate
from pandas import DataFrame

# type annotations
from typing import List, IO, Union


# program name is constructed from module file name
NAME = os.path.basename(__file__)[:-3].replace('_', '.')
PROGRAM = f'{__appname__} {NAME}'
PADDING = ' ' * len(PROGRAM)

USAGE = f"""\
usage: {PROGRAM} <schema>.<table> [--columns NAME [NAME...]] [--where CONDITION [CONDITION...]]
       {PADDING} [--output PATH] [--format FORMAT | ...] [--tablefmt FORMAT]
       {PADDING} [--limit COUNT | --no-limit] [--join] [--debug] [--dry-run]
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

The "where" clauses must be quoted. The output format will be inferred from
the file extension if possible, otherwise can be specified. If no output path
is given the format should be specified and data will be written to standard
output. The default format is ASCII. When writing to ASCII format, the --tablefmt
option specifies how to format the data (e.g., "plain", "psql", "latex", etc.).

Output is limited to 10 by default for safety. Use --no-limit to disable this 
behavior.

arguments:
<schema>.<table>             Name of the table.

options:
-c, --columns    NAME        Names of columns to include.
-o, --output     PATH        File path for output.
-w, --where      CONDITION   Quoted SQL conditional statements.
-l, --limit      COUNT       Limit number of records to fetch. (default: 10)
-a, --no-limit               Disable limit on number of records.
-j, --join                   Swap in fkey _id fields for _name fields.
    --dry-run                Show SQL without executing.
-d, --debug                  Show debugging messages.
-h, --help                   Show this message and exit.

formats:
-f, --format     FORMAT      Name of output format. (default: CSV)
  , --ascii
  , --json
  , --csv
  , --feather
  , --excel
  , --html

    --tablefmt   FORMAT      Format scheme for ASCII output.


{EPILOG}
"""

# initialize module level logger
log = logger.with_name(f'{__appname__}.{NAME}')


def to_ascii(self, output: Union[str, IO], tablefmt: str = 'plain') -> None:
    """Output writer for `pandas.DataFrame`."""
    content = tabulate(self.values.tolist(), list(self.columns), tablefmt=tablefmt)
    if isinstance(output, str):
        with open(output, 'w') as outfile:
            outfile.write(content)
    else:
        output.write(content)

# attach to DataFrame for consistency of interface
DataFrame.to_ascii = to_ascii


class DataSelectApp(Application):

    interface = Interface(PROGRAM, USAGE, HELP)

    source: str = None
    interface.add_argument('source', metavar='<schema>.<table>')

    columns: List[str] = []
    interface.add_argument('-c', '--columns', nargs='+', default=[])

    where: List[str] = []
    interface.add_argument('-w', '--where', nargs='+', default=[])

    output: str = None
    interface.add_argument('-o', '--output', default=None)
    ext_map: dict = {'.csv': 'csv', '.xlsx': 'excel', '.feather': 'feather',
                     '.html': 'html', '.json': 'json'}

    limit: int = 10
    no_limit: bool = False
    limit_group = interface.add_mutually_exclusive_group()
    limit_group.add_argument('-l', '--limit', type=int)
    limit_group.add_argument('-a', '--no-limit', action='store_true')

    join: bool = False
    interface.add_argument('-j', '--join', action='store_true')

    output_format: str = None
    formats: List[str] = ['ascii', 'csv', 'json', 'excel', 'html', 'feather']
    format_group = interface.add_mutually_exclusive_group()
    format_group.add_argument('-f', '--format', choices=formats, dest='output_format')
    for option in formats:
        format_group.add_argument(f'--{option}', dest=f'format_{option}', action='store_true')

    tablefmt: str = 'plain'
    tablefmts: List[str] = ['plain', 'simple', 'github', 'grid', 'fancy_grid', 'pipe', 
                            'orgtbl', 'jira', 'presto', 'psql', 'rst', 'mediawiki', 'moinmoin', 
                            'youtrack', 'html', 'latex', 'latex_raw', 'latex_booktabs', 'textile']
    interface.add_argument('-t', '--tablefmt', choices=tablefmts, default=tablefmt)

    dry_run: bool = False
    interface.add_argument('--dry-run', action='store_true')

    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')

    def run(self) -> None:
        """Run query."""

        if self.debug:
            for handler in log.handlers:
                handler.level = log.levels[0]

        limit = None if self.no_limit else self.limit
        schema, table = self.source.split('.')
        columns = self.columns

        # extract map of any specified format flags
        format_flags = {option: getattr(self, f'format_{option}') for option in self.formats}

        # allow for format flags
        for output_format, selected in format_flags.items():
            if selected is True:
                self.output_format = output_format

        # if a file extension is present, determine sensible format
        if self.output not in (None, '-') and self.output_format is None:
            _, file_ext = os.path.splitext(self.output)
            if file_ext in self.ext_map:
                log.debug(f'known file extension: "{file_ext}"')
                self.output_format = self.ext_map[file_ext]
            elif self.output_format is None and not any(format_flags.values()):
                log.critical(f'filetype not implemented: "{file_ext}"')
                return

        if self.output_format is None:
            self.output_format = 'ascii'

        # output is either a path or <stdout> instance
        if self.output in (None, '-'):
            self.output = sys.stdout

        # pre-construct parameters in case of dry-run
        params = dict(columns=columns, schema=schema, table=table, limit=limit,
                      where=self.where, orderby=None, ascending=True, join=self.join)

        if self.dry_run:
            sys.stdout.write(database.interface._make_select(**params))
            return

        # fetch all records
        data = database.select(set_index=False, **params)

        # determine writer method
        if self.output_format == 'ascii':
            writer = functools.partial(to_ascii, data, tablefmt=self.tablefmt)
        elif self.output_format == 'csv':
            writer = functools.partial(data.to_csv)
        elif self.output_format == 'json':
            writer = functools.partial(data.to_json, orient='records', lines=True)
        elif self.output_format == 'feather':
            data = data.reset_index()  # non-default indices are not serializable
            writer = data.to_feather
        else:
            writer = getattr(data, f'to_{self.output_format}')

        writer(self.output)


# inherit docstring from module
DataSelectApp.__doc__ = __doc__