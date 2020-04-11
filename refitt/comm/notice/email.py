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

"""
Send emails.
"""

# type annotations
from __future__ import annotations
from typing import List, Dict, Union, Optional

# standard libs
import os
import io
from abc import abstractproperty
from datetime import datetime
from smtplib import SMTP
from ssl import SSLContext, create_default_context
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

# external libs
from pandas import read_csv

# internal libs
from ...core.logging import Logger


# initialize module level logger
log = Logger.with_name(__name__)


class UserAuth:
    """
    A username and password.

    Example:
    >>> auth = UserAuth('me', 'my-password')
    >>> auth
    UserAuth(username="me", password="****")

    >>> auth.username
    "me"
    """

    _username: str
    _password: str

    def __init__(self, username: str, password: str) -> None:
        """Specify location of mail server."""
        self._username = str(username)
        self._password = str(password)

    @property
    def username(self) -> str:
        """The username."""
        return self._username

    @property
    def password(self) -> str:
        """The password."""
        return self._password

    def __str__(self) -> str:
        """String representation."""
        return f'{self.__class__.__name__}(username="{self.username}", password="****")'

    def __repr__(self) -> str:
        """Interactive representation."""
        return str(self)


# A MIME document with multipart/mixed will simply include all
# the attachments in sequential order (text / html / files).
# A MIME document with multipart/alternative will display with
# some priority and fallback (html before plain).
DEFAULT_MIME_TYPE = 'mixed'

# Email address can be specified as a single string or a list of strings.
# This applies for `recipients`, `cc`, and `bcc`.
ADDR_SPEC = Union[str, List[str]]

# Attachments can be specified in the parameters passed to the constructor
# as either a lone simple string, a list of file paths, or a dictionary
# with keys as the names to use for the attachment and file paths for values.
FILE_SPEC = Union[str, List[str], Dict[str, str]]


class Mail:
    """
    Construct and send email messages.

    All the message properties can be dynamically altered and the
    underlying MIME document will be modified inplace.

    Example
    -------

    Send a basic plain text email.
    >>> mail = Mail('me@mail.com', 'you@mail.com',
    ...             subject='Hello!', text='Hello, world!')

    Send an html email with plain text alternative.
    >>> mail = Mail('me@mail.com', ['you@mail.com', 'you2@mail.com'],
    ...             subject='Hello', text='Hello, world!', subtype='alternative')
    >>> mail.text = 'Hello, other!'
    >>> mail.html = '''
    ... <html>
    ...     <head></head>
    ...     <body>
    ...         <p>Hello, world!</p>
    ...     </body>
    ... </html>
    ... '''
    """

    _mime: MIMEMultipart = None
    _payload_index: Dict[str, int] = None
    _data: Dict[str, bytes] = None
    _bcc: List[str] = []  # not included in headers

    def __init__(self, *args, **kwargs) -> None:
        """Initialize email."""
        if len(args) == 0:
            self._null_constructor(**kwargs)
        elif len(args) == 1:
            self._move_constructor(*args)
        else:
            self._init_constructor(*args, **kwargs)

    def _null_constructor(self, subtype: str = DEFAULT_MIME_TYPE) -> None:
        """Initialize with empty `MIMEMultipart`."""
        self._mime = MIMEMultipart(subtype)
        self._payload_index = dict()
        self._data = dict()

    def _move_constructor(self, other: Union[Mail, MIMEMultipart]) -> None:
        """Moves/coerces existing email."""
        if isinstance(other, self.__class__):
            self._mime = other.mime
            self._payload_index = other._payload_index
            self._data = other._data
        else:
            raise TypeError(f'cannot convert {other} to type Email')

    def _init_constructor(self, from_addr: str, to_addr: ADDR_SPEC, *,
                          subject: str = None, cc: ADDR_SPEC = None, bcc: ADDR_SPEC = None,
                          text: str = None, html: str = None, attach: FILE_SPEC = None,
                          subtype: str = DEFAULT_MIME_TYPE) -> None:
        """Initialize message parts."""

        self._null_constructor(subtype=subtype)
        self.address = from_addr
        self.recipients = to_addr
        self.cc = cc
        self.bcc = bcc
        self.subject = subject
        self.date = formatdate(localtime=True)

        if text is not None:
            self.text = text

        if html is not None:
            self.html = html

        if attach is not None:
            self.attach(attach)

    @property
    def mime(self) -> MIMEMultipart:
        """Access to the MIME document."""
        return self._mime

    @property
    def address(self) -> Optional[str]:
        """The sender's address."""
        return self.mime['From']

    @address.setter
    def address(self, other: str) -> None:
        """Set the sender's address."""
        if self.mime['From'] is not None:
            del self.mime['From']
        self.mime['From'] = str(other)

    @property
    def recipients(self) -> Optional[List[str]]:
        """The recipients' addresses."""
        return [addr.strip() for addr in self.mime['To'].split(',')]

    @recipients.setter
    def recipients(self, other: ADDR_SPEC) -> None:
        """Set the recipients' addresses."""
        if self.mime['To'] is not None:
            del self.mime['To']
        recipients = [other] if isinstance(other, str) else list(other)
        self.mime['To'] = ', '.join(recipients)

    @property
    def cc(self) -> Optional[List[str]]:
        """The CC recipients' addresses."""
        addresses = self.mime['CC']
        if addresses is None:
            return []
        else:
            return [addr.strip() for addr in addresses.split(',')]

    @cc.setter
    def cc(self, other: ADDR_SPEC) -> None:
        """Set the CC recipients' addresses."""
        if self.mime['CC'] is not None:
            del self.mime['CC']
        if other is not None:
            recipients = [other] if isinstance(other, str) else list(other)
            self.mime['CC'] = ', '.join(recipients)

    @property
    def bcc(self) -> Optional[List[str]]:
        """The BCC recipients' addresses."""
        return self._bcc

    @bcc.setter
    def bcc(self, other: ADDR_SPEC) -> None:
        """Set the BCC recipients' addresses."""
        if other is None:
            self._bcc = []
        elif isinstance(other, str):
            self._bcc = [other]
        else:
            self._bcc = list(map(str, other))

    @property
    def date(self) -> Optional[str]:
        """The date of the message."""
        return self.mime['Date']

    @date.setter
    def date(self, other: str) -> None:
        """Set the date of the message."""
        if self.mime['Date'] is not None:
            del self.mime['Date']
        if other is not None:
            self.mime['Date'] = str(other)

    @property
    def subject(self) -> Optional[str]:
        """The subject of the message."""
        return self.mime['Subject']

    @subject.setter
    def subject(self, other: str) -> None:
        """Set the subject of the message."""
        if self.mime['Subject'] is not None:
            del self.mime['Subject']
        if other is not None:
            self.mime['Subject'] = str(other)

    def __getitem__(self, key: str) -> Optional[str]:
        """Get attachment."""
        if key not in self._payload_index:
            return None
        else:
            loc = self._payload_index[key]
            return self.mime.get_payload(loc).get_payload()

    def __setitem__(self, key: str, value: str) -> None:
        """Set attachment."""
        if key in self._payload_index:
            loc = self._payload_index[key]
            self.mime.get_payload(loc).set_payload(str(value))
        else:
            self.mime.attach(MIMEText(str(value), key))
            self._payload_index[key] = len(self._payload_index)

    @property
    def text(self) -> Optional[str]:
        """Access to text."""
        return self['plain']

    @text.setter
    def text(self, other: str) -> None:
        """Set text."""
        self['plain'] = other

    @property
    def html(self) -> Optional[str]:
        """Access to html."""
        return self['html']

    @html.setter
    def html(self, other: str) -> None:
        """Set html."""
        self['html'] = other

    # ways of specifying attachments
    _attach_methods: dict = {
        str: '_attach_file',
        list: '_attach_list',
        dict: '_attach_dict'
    }

    def _attach_file(self, path: str, label: str = None):
        """Load a local file from `path` and attach as MIMEApplication."""
        name = label if label is not None else os.path.basename(path)
        if name in ('plain', 'html'):
            raise ValueError(f'Cannot attach file with label="{name}", that name is reserved.')
        with open(path, mode='rb') as source:
            data = source.read()
            part = MIMEApplication(data, Name=name)
            part['Content-Disposition'] = f"attachment; filename=\"{name}\""
            self._data[name] = data
            if name in self._payload_index:
                loc = self._payload_index[name]
                self.mime.get_payload(loc).set_payload(part)
            else:
                self.mime.attach(part)
                self._payload_index[name] = len(self._payload_index)

    def _attach_list(self, paths: List[str]) -> None:
        """Attach each of a list of file `paths`."""
        for path in paths:
            self._attach_file(path)

    def _attach_dict(self, paths: Dict[str, str]) -> None:
        """Attach each of a list of file `paths` with specific names."""
        for name, path in paths.items():
            self._attach_file(path, name)

    def attach(self, file_spec: FILE_SPEC) -> None:
        """Load local `filepath` and attach as MIMEApplication."""
        try:
            attach_method = getattr(self, self._attach_methods[type(file_spec)])
            attach_method(file_spec)
        except KeyError as error:
            spec_type, = error.args
            raise TypeError(f'Unrecognized file specification: {spec_type}')

    @property
    def attachments(self) -> List[str]:
        """List of file attachment names."""
        return [name for name in self._payload_index if name not in ('plain', 'html')]

    def __len__(self) -> int:
        """Return length of MIMEMultipart (less one)."""
        return len(self._payload_index)

    def __str__(self) -> str:
        """Full mime as text string."""
        return self.mime.as_string()

    def __repr__(self) -> str:
        """String representation."""
        return str(self)


class Server:
    """
    A mail server.

    Example
    -------
    >>> server = Server('smtp.mail.com', 587)
    >>> server
    Server('smtp.gmail.com', 587)


    >>> mail = Mail('me@mail.com', 'you@mail.com',
    ...             subject='Hello!', text='Hello, world!')

    >>> auth = UserAuth('username', 'password')
    >>> with Server('smtp.mail.com', 587, auth) as server:
    ...     server.send(mail)
    """

    _host: str
    _port: int
    _auth: UserAuth = None

    _ssl: SSLContext = None
    _server: SMTP = None

    def __init__(self, host: str = 'localhost', port: int = 587, auth: UserAuth = None) -> None:
        """Specify location of mail server."""
        self._host = str(host)
        self._port = int(port)
        self._auth = auth

    @property
    def host(self) -> str:
        """The hostname for the mail server."""
        return self._host

    @property
    def port(self) -> int:
        """The port number for the mail server."""
        return self._port

    @property
    def auth(self) -> Optional[UserAuth]:
        """User authentication."""
        return self._auth

    @property
    def server(self) -> SMTP:
        """The mail server SMTP connection."""
        return self._server

    def __str__(self) -> str:
        """String representation."""
        return (f'Server(host="{self.host}", port={self.port}, '
                f'auth={self.auth})')

    def __repr__(self) -> str:
        """Interactive representation."""
        return str(self)

    def connect(self, **kwargs) -> None:
        """Connect to mail server."""
        self._server = SMTP(self.host, self.port, **kwargs)
        if self.auth is not None:
            self._ssl = create_default_context()
            self._server.starttls(context=self._ssl)
            self._server.login(self.auth.username, self.auth.password)

    def disconnect(self) -> None:
        """Disconnect from mail server."""
        if self._server is not None:
            self._server.quit()

    def send(self, mail: Mail) -> None:
        """Send email using mail server."""
        outgoing = mail.recipients + mail.cc + mail.bcc
        self.server.sendmail(mail.address, outgoing, str(mail))

    def __enter__(self) -> Server:
        """Connect to mail server."""
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        """Disconnect from mail server."""
        self.disconnect()


class Template(Mail):
    """An email message with a specifically formatted template."""

    @abstractproperty
    def required(self) -> int:
        """The number of required positional arguments."""


class TestMail(Template):
    """Basic test email."""

    message = "This is a test of REFITT's automated messaging system."
    required = 0

    def __init__(self, *args, **kwargs) -> None:
        """No attachments or subject allowed."""

        attachments = kwargs.pop('attach', None)
        if attachments:
            log.warning('ignore attachments for test message')

        text = kwargs.pop('text', None)
        if text is not None:
            log.warning('ignoring text body for test message')

        html = kwargs.pop('html', None)
        if html is not None:
            log.warning('ignoring html body for test message')

        subject = kwargs.pop('subject', None)
        if subject is not None:
            log.warning('ignore subject for test message')

        super().__init__(*args, **{'text': self.message, **kwargs})
        self.subject = f'REFITT Test ({self.date})'


RECOMMENDATION_TEMPLATE = """\
<html>
    <head></head>
    <body>
        <p>Hello, {name}.</p>
        
        <p>
        Attached are your recommended targets for tonight.
        This email is for convenience purposes. Log in at
        <a href="https://refitt.org">refitt.org</a> to adjust your notification
        preferences. Below is a preview of the first few targets.
        </p>
        <br>
        
        {table}
        
        <br>
        <p><em>Thanks!</em><br>
        REFITT Team<p>
        
        <p>--<br>
        This email was automatically generated by the REFITT system.<br>
        This information is current as of {date}.<br>
        Log in at <a href="https://refitt.org">refitt.org</a> for details.
        </p>
        <br>
    </body>
</html>
"""


class RecommendationMail(Template):
    """Recommendation email with a CSV of targets attached."""

    required = 1

    def __init__(self, name: str, *args, **kwargs) -> None:
        """
        Initialize template with a person's `name`.
        A single attachment is required to be a CSV file.
        """

        subject = kwargs.pop('subject', None)
        if subject is not None:
            log.warning('ignore subject for test message')

        # check attachments
        attachment = kwargs.pop('attach', None)
        if not attachment or len(attachment) != 1:
            raise ValueError('RecommendationMail requires a single file attachment.')
        if not isinstance(attachment, list):
            raise ValueError('RecommendationMail expected a length-1 list of attachments.')

        attachment, = attachment
        if not attachment.endswith('.csv'):
            raise ValueError(f'RecommendationMail requires a CSV file, given {attachment}.')

        # base initialization
        super().__init__(*args, **kwargs)

        # add stub html so it is first in the payload
        self.html = ''

        # add attachment (loads the raw data)
        time = datetime.utcnow().astimezone()
        stamp = time.strftime('%Y%m%d-%H%M%S')
        filename = f'recommendations-{stamp}.csv'
        self.attach({filename: attachment})

        # parse the CSV data
        data = read_csv(io.BytesIO(self._data[filename]))
        table = data.head(4).to_html(justify='right', index=False)

        # format html message
        date = time.strftime('%a, %d %b %Y %T UTC')
        self.html = RECOMMENDATION_TEMPLATE.format(name=name, table=table, date=date)
        self.subject = f'REFITT Recommendations ({date})'


# named templates and their classes
templates = {
    'test': TestMail,
    'recommend': RecommendationMail,
}

TEMPLATES = f"""\
test         {TestMail.__doc__}
recommend    {RecommendationMail.__doc__}\
"""