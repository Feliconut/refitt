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

"""Facility profile endpoints."""


# type annotations
from typing import Union

# standard libs
import json

# internal libs
from ....database.model import Client, Facility, IntegrityError, NotFound
from ..app import application
from ..response import endpoint, PayloadNotFound, PayloadMalformed, PayloadInvalid, ConstraintViolation
from ..auth import authenticated, authorization

# external libs
from flask import request


@application.route('/facility/<id_or_name>', methods=['GET'])
@endpoint('application/json')
@authenticated
@authorization(level=0)
def get_facility(admin: Client, id_or_name: Union[int, str]) -> dict:  # noqa: unused client
    """Query for existing facility profile."""
    try:
        facility_id = int(id_or_name)
        return {'facility': Facility.from_id(facility_id).to_json()}
    except ValueError:
        facility_name = str(id_or_name)
        return {'facility': Facility.from_name(facility_name).to_json()}


@application.route('/facility', methods=['POST'])
@endpoint('application/json')
@authenticated
@authorization(level=0)
def add_facility(admin: Client) -> dict:  # noqa: unused client
    """Add new facility profile."""
    payload = request.data
    if not payload:
        raise PayloadNotFound('Missing JSON data')
    try:
        profile = json.loads(payload.decode())
    except json.JSONDecodeError as error:
        raise PayloadMalformed('Invalid JSON data') from error
    try:
        Facility(**profile)
    except TypeError as error:
        raise PayloadInvalid('Invalid parameters in JSON data') from error
    try:
        facility_id = profile.pop('id', None)
        if not facility_id:
            facility_id = Facility.add(profile)
        else:
            Facility.update(facility_id, **profile)
    except IntegrityError as error:
        raise ConstraintViolation(str(error.args[0])) from error
    return {'facility': {'id': facility_id}}


@application.route('/facility/<int:facility_id>', methods=['PUT'])
@endpoint('application/json')
@authenticated
@authorization(level=0)
def update_facility(admin: Client, facility_id: int) -> dict:  # noqa: unused client
    """Update facility profile attributes."""
    try:
        Facility.update(facility_id, **request.args)
    except IntegrityError as error:
        raise ConstraintViolation(str(error.args[0])) from error
    return {'facility': {'id': facility_id}}


@application.route('/facility/<int:facility_id>', methods=['DELETE'])
@endpoint('application/json')
@authenticated
@authorization(level=0)
def delete_facility(admin: Client, facility_id: int) -> dict:  # noqa: unused client
    """Delete a facility profile (assuming no existing relationships)."""
    try:
        Facility.delete(facility_id)
    except IntegrityError as error:
        raise ConstraintViolation(str(error.args[0])) from error
    return {'facility': {'id': facility_id}}


@application.route('/facility/<int:facility_id>/user', methods=['GET'])
@endpoint('application/json')
@authenticated
@authorization(level=0)
def get_all_facility_users(admin: Client, facility_id: int) -> dict:  # noqa: unused client
    """Query for users related to the given facility."""
    return {
        'user': [
            user.to_json()
            for user in Facility.from_id(facility_id).users()
        ]
    }


@application.route('/facility/<int:facility_id>/user/<int:user_id>', methods=['GET'])
@endpoint('application/json')
@authenticated
@authorization(level=0)
def get_facility_user(admin: Client, facility_id: int, user_id: int) -> dict:  # noqa: unused client
    """Query for a user related to the given facility."""
    users = [user.to_json() for user in Facility.from_id(facility_id).users() if user.id == user_id]
    if not users:
        raise NotFound(f'User ({user_id}) not associated with facility ({facility_id})')
    else:
        return {'user': users[0]}


@application.route('/facility/<int:facility_id>/user/<int:user_id>', methods=['PUT'])
@endpoint('application/json')
@authenticated
@authorization(level=0)
def add_facility_user_association(admin: Client, facility_id: int, user_id: int) -> dict:  # noqa: unused client
    """Associate facility with the given user."""
    Facility.from_id(facility_id).add_user(user_id)
    return {}


@application.route('/facility/<int:facility_id>/user/<int:user_id>', methods=['DELETE'])
@endpoint('application/json')
@authenticated
@authorization(level=0)
def delete_facility_user_association(admin: Client, facility_id: int, user_id: int) -> dict:  # noqa: unused client
    """Query for facilities related to the given user."""
    Facility.from_id(facility_id).delete_user(user_id)
    return {}
