#!/usr/bin/env python3

import datetime as dt
from unittest import mock
from rest_framework import status as http_status
import pytz
from django.utils import timezone

import pytest
from pytest import raises

from api.base.settings.defaults import API_BASE
from api.providers.workflows import Workflows

from framework.exceptions import HTTPError

from osf.migrations import update_provider_auth_groups
from osf.models import RegistrationSchema, DraftRegistration
from osf.utils import permissions
from website.project.metadata.schemas import _name_to_id
from website.util import api_url_for

from osf_tests.factories import (
    AuthUserFactory,
    DraftRegistrationFactory,
    EmbargoFactory,
    NodeFactory,
    RegistrationFactory,
    RegistrationProviderFactory
)
from tests.json_api_test_app import JSONAPITestApp
from tests.test_registrations.base import RegistrationsTestBase

from tests.base import get_default_metaschema

SCHEMA_VERSION = 2


@pytest.mark.django_db
class TestModeratorRegistrationViews:

    @pytest.fixture
    def app(self):
        return JSONAPITestApp()

    @pytest.fixture
    def moderator(self):
        return AuthUserFactory()

    @pytest.fixture
    def provider(self, moderator):
        provider = RegistrationProviderFactory()
        update_provider_auth_groups()
        provider.get_group('moderator').user_set.add(moderator)
        provider.reviews_workflow = Workflows.PRE_MODERATION.value
        provider.save()
        return provider

    @pytest.fixture
    def embargoed_registration(self, provider):
        embargo = EmbargoFactory()
        registration = embargo.target_registration
        registration.provider = provider
        registration.update_moderation_state()
        registration.save()
        return registration


    # API paths for registrations that are not publically available on non-public Registrations
    PROTECTED_REGISTRATION_SUB_ROUTES = [
        '',
        'bibliographic_contributors',
        'children',
        'comments',
        'implicit_contributors',
        'files',
        'citation',
        'forks',
        'identifiers',
        'institutions',
        'linked_nodes',
        'linked_registrations',
        'linked_by_nodes',
        'linked_by_registrations',
        'logs',
        'node_links',
        'relationships/institutions',
        'relationships/linked_nodes',
        'relationships/linked_registrations',
        'relationships/subjects',
        'subjects',
        'wikis',
    ]
    @pytest.fixture(params=PROTECTED_REGISTRATION_SUB_ROUTES)
    def registration_subpath(self, request, embargoed_registration):
        url = f'/{API_BASE}registrations/{embargoed_registration._id}/{request.param}'
        if request.param:
            url += '/'
        return url


    def test_moderator_cannot_view_subpath_of_initial_registration(
        self, app, embargoed_registration, moderator, registration_subpath):
        # Moderators should not have non-standard access to a registration
        # before it is submitted for moderation by its authors
        assert embargoed_registration.moderation_state == 'initial'

        resp = app.get(registration_subpath, auth=moderator.auth, expect_errors=True)
        assert resp.status_code == 403

    def test_moderator_can_view_subpath_of_submitted_registration(
        self, app, embargoed_registration, moderator, registration_subpath):
        # Moderators may need to see details of the pending registration
        # in order to determine whether to give approval
        embargoed_registration.embargo.accept()
        embargoed_registration.refresh_from_db()
        assert embargoed_registration.moderation_state == 'pending'

        resp = app.get(registration_subpath, auth=moderator.auth)
        assert resp.status_code == 200

    def test_moderator_can_viw_subpath_of_embargoed_registration(
        self, app, embargoed_registration, moderator, registration_subpath):
        # Moderators may need to see details of an embargoed registration
        # to determine if there is a need to withdraw before it becomes public
        embargoed_registration.embargo.accept()
        embargoed_registration.embargo.accept(user=moderator)
        embargoed_registration.refresh_from_db()
        assert embargoed_registration.moderation_state == 'embargo'

        resp = app.get(registration_subpath, auth=moderator.auth)
        assert resp.status_code == 200
