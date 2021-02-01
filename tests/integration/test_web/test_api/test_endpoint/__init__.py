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

"""Integration tests for API endpoints."""


# type annotations
from typing import Tuple, Dict, Callable

# standard libs
from abc import ABC, abstractproperty
from datetime import timedelta
from functools import lru_cache

# internal libs
from refitt.web.request import format_request
from refitt.web.token import JWT, Secret
from refitt.web.api.auth import AuthenticationNotFound, AuthenticationInvalid, PermissionDenied
from refitt.web.api.response import RESPONSE_MAP, TokenNotFound, TokenInvalid, TokenExpired
from refitt.database.model import User, Client
from tests.integration.test_web.test_api import temp_secret, temp_revoke_access

# external libs
import requests


class EndpointBase(ABC):
    """Shared logic and helper methods for Endpoint test classes."""

    @abstractproperty
    def route(self) -> str:
        """Base route needed for common tests."""

    @abstractproperty
    def admin(self) -> str:
        """User alias for admin role if needed."""

    @abstractproperty
    def user(self) -> str:
        """User alias for api target if needed."""

    @staticmethod
    def create_token(client_id: int) -> str:
        return JWT(sub=client_id, exp=timedelta(minutes=15)).encrypt()

    @lru_cache(maxsize=None)
    def get_client(self, user_alias: str) -> Client:
        return Client.from_user(User.from_alias(user_alias).id)

    methods: Dict[str, Callable[..., requests.Response]] = {
        'get': requests.get,
        'put': requests.put,
        'post': requests.post,
        'delete': requests.delete,
    }

    def make_request(self, method: str, route: str, client_id: int, data: dict = None, **params) -> Tuple[int, dict]:
        token = self.create_token(client_id)
        response = self.methods[method](format_request(route), params=params, json=data,
                                        headers={'Authorization': f'Bearer {token}'})
        return response.status_code, response.json()

    def get(self, route: str, client_id: int, data: dict = None, **params) -> Tuple[int, dict]:
        return self.make_request('get', route, client_id, data=data, params=params)

    def put(self, route: str, client_id: int, data: dict = None, **params) -> Tuple[int, dict]:
        return self.make_request('put', route, client_id, data=data, params=params)

    def post(self, route: str, client_id: int, data: dict = None, **params) -> Tuple[int, dict]:
        return self.make_request('post', route, client_id, data=data, params=params)

    def delete(self, route: str, client_id: int, data: dict = None, **params) -> Tuple[int, dict]:
        return self.make_request('delete', route, client_id, data=data, params=params)


class LoginEndpoint(EndpointBase, ABC):
    """Authentication w/ key:secret common tests."""

    def test_auth_not_found(self) -> None:
        response = requests.get(format_request(self.route))
        assert response.status_code == RESPONSE_MAP[AuthenticationNotFound]
        assert response.json() == {'Status': 'Error',
                                   'Message': 'Missing key:secret in header'}

    def test_auth_key_invalid(self) -> None:
        url = format_request(self.route)
        response = requests.get(url, auth=('my-key', 'my-secret'))
        assert response.status_code == RESPONSE_MAP[AuthenticationInvalid]
        assert response.json() == {'Status': 'Error',
                                   'Message': 'Client key invalid'}

    def test_auth_secret_not_real(self) -> None:
        client = Client.from_user(User.from_alias('tomb_raider').id)
        response = requests.get(format_request(self.route), auth=(client.key, 'my-secret'))
        assert response.status_code == RESPONSE_MAP[AuthenticationInvalid]
        assert response.json() == {'Status': 'Error',
                                   'Message': 'Client secret invalid'}

    def test_auth_secret_invalid(self) -> None:
        client = Client.from_user(User.from_alias('tomb_raider').id)
        response = requests.get(format_request(self.route), auth=(client.key, Secret.generate().value))
        assert response.status_code == RESPONSE_MAP[AuthenticationInvalid]
        assert response.json() == {'Status': 'Error',
                                   'Message': 'Client secret invalid'}

    def test_auth_access_revoked(self) -> None:
        client = Client.from_user(User.from_alias('tomb_raider').id)
        with temp_secret(client.id) as secret:
            with temp_revoke_access(client.id):
                response = requests.get(format_request(self.route), auth=(client.key, secret.value))
                assert response.status_code == RESPONSE_MAP[PermissionDenied]
                assert response.json() == {'Status': 'Error',
                                           'Message': 'Access has been revoked'}


class Endpoint(EndpointBase, ABC):
    """Automatically test authentication and authorization."""

    def test_token_missing(self) -> None:
        response = requests.get(format_request(self.route))
        assert response.status_code == RESPONSE_MAP[TokenNotFound]
        assert response.json() == {'Status': 'Error',
                                   'Message': 'Expected "Authorization: Bearer <token>" in header'}

    def test_token_invalid(self) -> None:
        response = requests.get(format_request(self.route), headers={'Authorization': 'Bearer bad-token'})
        content = response.json()
        assert response.status_code == RESPONSE_MAP[TokenInvalid]
        assert content['Status'] == 'Error'
        assert content['Message'] == f'Token invalid: \'bad...ken\''

    def test_token_expired(self) -> None:
        client = self.get_client('tomb_raider')
        token = JWT(sub=client.id, exp=timedelta(minutes=-15)).encrypt()
        response = requests.get(url = format_request(self.route), headers={'Authorization': f'Bearer {token}'})
        content = response.json()
        assert response.status_code == RESPONSE_MAP[TokenExpired]
        assert content['Status'] == 'Error'
        assert content['Message'] == 'Token expired'

    def test_access_revoked(self) -> None:
        client = self.get_client(self.user)
        with temp_revoke_access(client.id):
            status, payload = self.get(self.route, client_id=client.id)
            assert status == RESPONSE_MAP[PermissionDenied]
            assert payload == {'Status': 'Error',
                               'Message': 'Access has been revoked'}
