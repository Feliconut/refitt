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

"""Connection and interface to database."""

# standard libs
import os
from typing import NamedTuple

# internal libs
from ..__meta__ import __appname__
from ..core.config import HOME
from ..core.logging import logger

# external libs
from sshtunnel import SSHTunnelForwarder
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


# initialize module level logger
log = logger.with_name(f'{__appname__}.database.client')


class ServerAddress(NamedTuple):
    """Combines a `host` and `port`."""
    host: str
    port: int


class UserAuth(NamedTuple):
    """A username and password pair."""
    username: str
    password: str = None

    def __str__(self) -> str:
        """String representation."""
        return f'{self.__class__.__name__}(username="{self.username}", password="****")'

    def __repr__(self) -> str:
        """Interactive representation."""
        return f'{self.__class__.__name__}(username="{self.username}", password="****")'


class SSHTunnel:
    """Wraps `sshtunnel.SSHTunnelForwarder`."""

    # host:port configuration
    _ssh: ServerAddress = None
    _remote: ServerAddress = None
    _local: ServerAddress = None

    # username/password
    _auth: UserAuth = None
    _pkey: str = None  # for password-less

    # the ssh-tunnel server
    _forwarder: SSHTunnelForwarder = None


    def __init__(self, ssh: ServerAddress, auth: UserAuth,
                 remote: ServerAddress, local: ServerAddress,
                 keyfile: str = f'{HOME}/.ssh/id_rsa') -> None:

        self.ssh = ssh
        self.remote = remote
        self.local = local
        self.auth = auth

        if os.path.isfile(keyfile):
            self.pkey = keyfile

        self.forwarder = SSHTunnelForwarder(
            (self.ssh.host, self.ssh.port),
            ssh_username=self.auth.username,
            ssh_password=self.auth.password, ssh_pkey=self.pkey,
            remote_bind_address=(self.remote.host, self.remote.port),
            local_bind_address=(self.local.host, self.local.port))

    @property
    def ssh(self) -> ServerAddress:
        """SSH server address."""
        return self._ssh

    @ssh.setter
    def ssh(self, other: ServerAddress) -> None:
        """Set SSH server address."""
        if isinstance(other, ServerAddress):
            self._ssh = other
        else:
            raise TypeError(f'{self.__class__.__name__}.ssh expects {ServerAddress}')

    @property
    def remote(self) -> ServerAddress:
        """Remote server address."""
        return self._remote

    @remote.setter
    def remote(self, other: ServerAddress) -> None:
        """Set remote server address."""
        if isinstance(other, ServerAddress):
            self._remote = other
        else:
            raise TypeError(f'{self.__class__.__name__}.remote expects {ServerAddress}')

    @property
    def local(self) -> ServerAddress:
        """Local server address."""
        return self._local

    @local.setter
    def local(self, other: ServerAddress) -> None:
        """Set local server address."""
        if isinstance(other, ServerAddress):
            self._local = other
        else:
            raise TypeError(f'{self.__class__.__name__}.local expects {ServerAddress}')

    @property
    def auth(self) -> UserAuth:
        """User authentication for the ssh server."""
        return self._auth

    @auth.setter
    def auth(self, other: UserAuth) -> None:
        """Set user authentication for the ssh server."""
        if isinstance(other, UserAuth):
            self._auth = other
        else:
            raise TypeError(f'{self.__class__.__name__}.auth expects {UserAuth}')

    @property
    def pkey(self) -> str:
        """SSH keyfile (e.g., ~/.ssh/id_rsa)."""
        return self._pkey

    @pkey.setter
    def pkey(self, other: str) -> None:
        """Set SSH keyfile (e.g., ~/.ssh/id_rsa)."""
        if not isinstance(other, str):
            raise TypeError(f'{self.__class__.__name__}.pkey expects {str}')
        elif not os.path.isfile(other):
            raise FileNotFoundError(other)
        else:
            self._pkey = other

    @property
    def forwarder(self) -> SSHTunnelForwarder:
        """`SSHTunnelForwarder` instance."""
        return self._forwarder

    @forwarder.setter
    def forwarder(self, other: SSHTunnelForwarder) -> None:
        """Set `SSHTunnelForwarder` instance."""
        if isinstance(other, SSHTunnelForwarder):
            self._forwarder = other
        else:
            raise TypeError(f'{self.__class__.__name__}.forwarder expects {SSHTunnelForwarder}')

    def __str__(self) -> str:
        """String representation."""
        cls_ = self.__class__.__name__
        pad_ = ' ' * len(cls_)
        return (f'{cls_}(ssh={self.ssh},\n{pad_} local={self.local},\n'
                f'{pad_} remote={self.remote},\n{pad_} auth={self.auth},\n'
                f'{pad_} pkey={self.pkey})')

    def __repr__(self) -> str:
        """String representation."""
        return str(self)


class DatabaseClient:
    """Connect to a database (optionally via an SSH tunnel)."""

    # connection details
    _server: ServerAddress = ServerAddress('localhost', 5432)
    _auth: UserAuth = None
    _database: str = None

    # SQLAlchemy database engine
    _engine: Engine = None

    # tunnel instance
    _tunnel: SSHTunnel = None

    def __init__(self, server: ServerAddress, auth: UserAuth,
                 database: str) -> None:
        """Initialize database connection details."""

        self.server = server
        self.auth = auth
        self.database = database

    @property
    def server(self) -> ServerAddress:
        """Database server address."""
        return self._server

    @server.setter
    def server(self, other: ServerAddress) -> None:
        """Set database server address."""
        if isinstance(other, ServerAddress):
            self._server = other
        else:
            raise TypeError(f'{self.__class__.__name__}.server expects {ServerAddress}')

    @property
    def auth(self) -> UserAuth:
        """User authentication for the database server."""
        return self._auth

    @auth.setter
    def auth(self, other: UserAuth) -> None:
        """Set user authentication for the database server."""
        if isinstance(other, UserAuth):
            self._auth = other
        else:
            raise TypeError(f'{self.__class__.__name__}.auth expects {UserAuth}')

    @property
    def database(self) -> str:
        """Database name."""
        return self._database

    @database.setter
    def database(self, other: str) -> None:
        """Set database name."""
        if isinstance(other, str):
            self._database = other
        else:
            raise TypeError(f'{self.__class__.__name__}.database expects {str}')

    @property
    def engine(self) -> Engine:
        """Database engine instance."""
        return self._engine

    @engine.setter
    def engine(self, other: Engine) -> None:
        """Set database engine instance."""
        if isinstance(other, Engine):
            self._engine = other
        else:
            raise TypeError(f'{self.__class__.__name__}.engine expects {Engine}')

    @property
    def tunnel(self) -> SSHTunnel:
        """SSHTunnel instance."""
        return self._tunnel

    @tunnel.setter
    def tunnel(self, other: SSHTunnel) -> None:
        """Set SSHTunnel instance."""
        if isinstance(other, SSHTunnel):
            self._tunnel = other
            self.server = other.local
        else:
            raise TypeError(f'{self.__class__.__name__}.tunnel expects {SSHTunnel}')

    def connect(self) -> None:
        """Initiate the connection to the database."""
        log.debug(f'connecting to "{self.database}" at {self.server.host}:{self.server.port}')
        username, password = tuple(self.auth)
        host, port = tuple(self.server)
        self._engine = create_engine(f'postgresql://{username}:{password}@{host}:{port}/{self.database}')
        log.debug(f'connected to "{self.database}" at {self.server.host}:{self.server.port}')

    def close(self) -> None:
        """Close database connection and ssh-tunnel if necessary."""
        self.engine.dispose()
        log.debug(f'disconnected from "{self.database}" at {self.server.host}:{self.server.port}')
        if self.tunnel is not None:
            self.tunnel.forwarder.__exit__()
            log.debug(f'disconnected SSH tunnel')

    def __enter__(self) -> 'DatabaseClient':
        """Context manager."""
        self.connect()
        return self

    def __exit__(self, exc_tb, exc_type, exc_value) -> None:
        """Context manager exit."""
        self.close()

    def use_tunnel(self, ssh: ServerAddress, auth: UserAuth = None,
                   local: ServerAddress=ServerAddress('localhost', 54320)) -> None:
        """Establish an ssh-tunnel."""
        auth_ = auth if auth is not None else self.auth
        self.tunnel = SSHTunnel(ssh=ssh, auth=auth_, remote=self.server, local=local)
        self.tunnel.forwarder.start()
        return self
