import mock
import pytest

from framework.auth.core import Auth
from api_tests.nodes.views.test_node_draft_registration_list import (
    TestDraftRegistrationList,
    TestDraftRegistrationCreate
)
from api.base.settings.defaults import API_BASE

from osf.migrations import ensure_invisible_and_inactive_schema
from osf.models import DraftRegistration, NodeLicense, RegistrationProvider
from osf_tests.factories import (
    RegistrationFactory,
    CollectionFactory,
    ProjectFactory,
    AuthUserFactory,
    InstitutionFactory
)
from osf.utils.permissions import READ, WRITE, ADMIN

from website import mails, settings


@pytest.fixture(autouse=True)
def invisible_and_inactive_schema():
    return ensure_invisible_and_inactive_schema()


@pytest.mark.django_db
class TestDraftRegistrationListNewWorkflow(TestDraftRegistrationList):
    @pytest.fixture()
    def url_draft_registrations(self, project_public):
        return '/{}draft_registrations/?'.format(API_BASE)

    # Overrides TestDraftRegistrationList
    def test_osf_group_with_admin_permissions_can_view(self):
        # DraftRegistration endpoints permissions are not calculated from the node
        return

    # Overrides TestDraftRegistrationList
    def test_cannot_view_draft_list(
            self, app, user_write_contrib, project_public,
            user_read_contrib, user_non_contrib, draft_registration,
            url_draft_registrations, group, group_mem):

        # test_read_only_contributor_can_view_draft_list
        res = app.get(
            url_draft_registrations,
            auth=user_read_contrib.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == 1

        #   test_read_write_contributor_can_view_draft_list
        res = app.get(
            url_draft_registrations,
            auth=user_write_contrib.auth)
        assert res.status_code == 200
        assert len(res.json['data']) == 1

        #   test_logged_in_non_contributor_can_view_draft_list
        res = app.get(
            url_draft_registrations,
            auth=user_non_contrib.auth,
            expect_errors=True)
        assert res.status_code == 200
        assert len(res.json['data']) == 0

        #   test_unauthenticated_user_cannot_view_draft_list
        res = app.get(url_draft_registrations, expect_errors=True)
        assert res.status_code == 401


class TestDraftRegistrationCreateWithNode(TestDraftRegistrationCreate):

    # Overrides `url_draft_registrations` in `TestDraftRegistrationCreate`
    @pytest.fixture()
    def url_draft_registrations(self, project_public):
        return '/{}draft_registrations/?'.format(API_BASE)

    # Overrides `payload` in TestDraftRegistrationCreate`
    @pytest.fixture()
    def payload(self, metaschema_open_ended, provider, project_public):
        return {
            'data': {
                'type': 'draft_registrations',
                'attributes': {},
                'relationships': {
                    'registration_schema': {
                        'data': {
                            'type': 'registration_schema',
                            'id': metaschema_open_ended._id
                        }
                    },
                    'branched_from': {
                        'data': {
                            'type': 'nodes',
                            'id': project_public._id
                        }
                    },
                    'provider': {
                        'data': {
                            'type': 'registration-providers',
                            'id': provider._id,
                        }
                    }
                }
            }
        }

    # Temporary alternative provider that supports `metaschema_open_ended` in `TestDraftRegistrationCreate`
    # This provider is created to fix the first 3 tests in this test class due to test DB changes with the
    # Django 3 Upgrade. A long-term solution is to create and/or use dedicated schemas for testing.
    @pytest.fixture()
    def provider_alt(self, metaschema_open_ended):
        default_provider = RegistrationProvider.get_default()
        default_provider.schemas.add(metaschema_open_ended)
        default_provider.save()
        return default_provider

    # Similarly, this is a temporary alternative payload that uses the above `provider_alt`.
    @pytest.fixture()
    def payload_alt(self, payload, provider_alt):
        new_payload = payload.copy()
        new_payload['data']['relationships']['provider']['data']['id'] = provider_alt._id
        return new_payload

    # Overrides TestDraftRegistrationList
    def test_cannot_create_draft_errors(self, app, user, payload_alt, project_public, url_draft_registrations):
        #   test_cannot_create_draft_from_a_registration
        registration = RegistrationFactory(
            project=project_public, creator=user)
        payload_alt['data']['relationships']['branched_from']['data']['id'] = registration._id
        res = app.post_json_api(
            url_draft_registrations, payload_alt, auth=user.auth,
            expect_errors=True)
        assert res.status_code == 404

    #   test_cannot_create_draft_from_deleted_node
        project = ProjectFactory(is_public=True, creator=user)
        project.is_deleted = True
        project.save()
        payload_alt['data']['relationships']['branched_from']['data']['id'] = project._id
        res = app.post_json_api(
            url_draft_registrations, payload_alt,
            auth=user.auth, expect_errors=True)
        assert res.status_code == 410
        assert res.json['errors'][0]['detail'] == 'The requested node is no longer available.'

    #   test_cannot_create_draft_from_collection
        collection = CollectionFactory(creator=user)
        payload_alt['data']['relationships']['branched_from']['data']['id'] = collection._id
        res = app.post_json_api(
            url_draft_registrations, payload_alt, auth=user.auth,
            expect_errors=True)
        assert res.status_code == 404

    def test_draft_registration_attributes_copied_from_node(self, app, project_public,
            url_draft_registrations, user, payload_alt):

        write_contrib = AuthUserFactory()
        read_contrib = AuthUserFactory()

        GPL3 = NodeLicense.objects.get(license_id='GPL3')
        project_public.set_node_license(
            {
                'id': GPL3.license_id,
                'year': '1998',
                'copyrightHolders': ['Grapes McGee']
            },
            auth=Auth(user),
            save=True
        )

        project_public.add_contributor(write_contrib, WRITE)
        project_public.add_contributor(read_contrib, READ)

        res = app.post_json_api(url_draft_registrations, payload_alt, auth=write_contrib.auth, expect_errors=True)
        assert res.status_code == 201
        res = app.post_json_api(url_draft_registrations, payload_alt, auth=read_contrib.auth, expect_errors=True)
        assert res.status_code == 403

        res = app.post_json_api(url_draft_registrations, payload_alt, auth=user.auth)
        assert res.status_code == 201
        attributes = res.json['data']['attributes']
        assert attributes['title'] == project_public.title
        assert attributes['description'] == project_public.description
        assert attributes['category'] == project_public.category
        assert set(attributes['tags']) == set([tag.name for tag in project_public.tags.all()])
        assert attributes['node_license']['year'] == '1998'
        assert attributes['node_license']['copyright_holders'] == ['Grapes McGee']

        relationships = res.json['data']['relationships']

        assert 'affiliated_institutions' in relationships
        assert 'subjects' in relationships
        assert 'contributors' in relationships

    def test_cannot_create_draft(
            self, app, user_write_contrib,
            user_read_contrib, user_non_contrib,
            project_public, payload_alt, group,
            url_draft_registrations, group_mem):

        #   test_write_only_contributor_cannot_create_draft
        assert user_write_contrib in project_public.contributors.all()
        res = app.post_json_api(
            url_draft_registrations,
            payload_alt,
            auth=user_write_contrib.auth,
            expect_errors=True)
        assert res.status_code == 201

    #   test_read_only_contributor_cannot_create_draft
        assert user_read_contrib in project_public.contributors.all()
        res = app.post_json_api(
            url_draft_registrations,
            payload_alt,
            auth=user_read_contrib.auth,
            expect_errors=True)
        assert res.status_code == 403

    #   test_non_authenticated_user_cannot_create_draft
        res = app.post_json_api(
            url_draft_registrations,
            payload_alt, expect_errors=True)
        assert res.status_code == 401

    #   test_logged_in_non_contributor_cannot_create_draft
        res = app.post_json_api(
            url_draft_registrations,
            payload_alt,
            auth=user_non_contrib.auth,
            expect_errors=True)
        assert res.status_code == 403

    #   test_group_admin_cannot_create_draft
        res = app.post_json_api(
            url_draft_registrations,
            payload_alt,
            auth=group_mem.auth,
            expect_errors=True)
        assert res.status_code == 201

    #   test_group_write_contrib_cannot_create_draft
        project_public.remove_osf_group(group)
        project_public.add_osf_group(group, WRITE)
        res = app.post_json_api(
            url_draft_registrations,
            payload_alt,
            auth=group_mem.auth,
            expect_errors=True)
        assert res.status_code == 201

    def test_create_project_based_draft_does_not_email_initiator(
            self, app, user, url_draft_registrations, payload):
        post_url = url_draft_registrations + 'embed=branched_from&embed=initiator'
        with mock.patch.object(mails, 'send_mail') as mock_send_mail:
            app.post_json_api(post_url, payload, auth=user.auth)

        assert not mock_send_mail.called

    def test_affiliated_institutions_are_copied_from_node_no_institutions(self, app, user, url_draft_registrations, payload):
        """
        Draft registrations that are based on projects get those project's user institutional affiliation,
        those "no-project" registrations inherit the user's institutional affiliation.

        This tests a scenario where a user bases a registration on a node without affiliations, and so the
        draft registration has no institutional affiliation from the user or the node.
        """
        project = ProjectFactory(is_public=True, creator=user)
        payload['data']['relationships']['branched_from']['data']['id'] = project._id
        res = app.post_json_api(
            url_draft_registrations,
            payload,
            auth=user.auth,
        )
        assert res.status_code == 201
        draft_registration = DraftRegistration.load(res.json['data']['id'])
        assert not draft_registration.affiliated_institutions.exists()

    def test_affiliated_institutions_are_copied_from_node(self, app, user, url_draft_registrations, payload):
        """
        Draft registrations that are based on projects get those project's user institutional affiliation,
        those "no-project" registrations inherit the user's institutional affiliation.

        This tests a scenario where a user bases their registration on a project that has a current institutional
        affiliation which is copied over to the draft registrations.
        """
        institution = InstitutionFactory()

        project = ProjectFactory(is_public=True, creator=user)
        project.affiliated_institutions.add(institution)
        payload['data']['relationships']['branched_from']['data']['id'] = project._id
        res = app.post_json_api(
            url_draft_registrations,
            payload,
            auth=user.auth,
        )
        assert res.status_code == 201
        draft_registration = DraftRegistration.load(res.json['data']['id'])
        assert list(draft_registration.affiliated_institutions.all()) == list(project.affiliated_institutions.all())

    def test_affiliated_institutions_are_copied_from_user(self, app, user, url_draft_registrations, payload):
        """
        Draft registrations that are based on projects get those project's user institutional affiliation,
        those "no-project" registrations inherit the user's institutional affiliation.
        """
        institution = InstitutionFactory()
        user.add_or_update_affiliated_institution(institution)

        del payload['data']['relationships']['branched_from']
        res = app.post_json_api(
            url_draft_registrations,
            payload,
            auth=user.auth,
        )
        assert res.status_code == 201
        draft_registration = DraftRegistration.load(res.json['data']['id'])
        assert list(draft_registration.affiliated_institutions.all()) == list(user.get_affiliated_institutions())


class TestDraftRegistrationCreateWithoutNode(TestDraftRegistrationCreate):
    @pytest.fixture()
    def url_draft_registrations(self):
        return '/{}draft_registrations/?'.format(API_BASE)

    # Overrides TestDraftRegistrationList
    def test_admin_can_create_draft(
            self, app, user, url_draft_registrations,
            payload, metaschema_open_ended):
        url = '{}embed=branched_from&embed=initiator'.format(url_draft_registrations)
        res = app.post_json_api(url, payload, auth=user.auth)

        assert res.status_code == 201
        data = res.json['data']
        assert metaschema_open_ended._id in data['relationships']['registration_schema']['links']['related']['href']
        assert data['attributes']['registration_metadata'] == {}
        assert data['relationships']['provider']['links']['related']['href'] == \
               f'{settings.API_DOMAIN}v2/providers/registrations/{RegistrationProvider.default__id}/'

        assert data['embeds']['branched_from']['data']['id'] == DraftRegistration.objects.get(_id=data['id']).branched_from._id
        assert data['embeds']['initiator']['data']['id'] == user._id

        draft = DraftRegistration.load(data['id'])
        assert draft.creator == user
        assert draft.has_permission(user, ADMIN) is True

    def test_create_no_project_draft_emails_initiator(
            self, app, user, url_draft_registrations, payload):
        post_url = url_draft_registrations + 'embed=branched_from&embed=initiator'

        # Intercepting the send_mail call from website.project.views.contributor.notify_added_contributor
        with mock.patch.object(mails, 'send_mail') as mock_send_mail:
            resp = app.post_json_api(post_url, payload, auth=user.auth)
        assert mock_send_mail.called

        # Python 3.6 does not support mock.call_args.args/kwargs
        # Instead, mock.call_args[0] is positional args, mock.call_args[1] is kwargs
        # (note, this is compatible with later versions)
        mock_send_kwargs = mock_send_mail.call_args[1]
        assert mock_send_kwargs['mail'] == mails.CONTRIBUTOR_ADDED_DRAFT_REGISTRATION
        assert mock_send_kwargs['user'] == user
        assert mock_send_kwargs['node'] == DraftRegistration.load(resp.json['data']['id'])

    def test_create_draft_with_provider(self, app, user, url_draft_registrations, non_default_provider, payload_with_non_default_provider):
        res = app.post_json_api(url_draft_registrations, payload_with_non_default_provider, auth=user.auth)
        assert res.status_code == 201
        data = res.json['data']
        assert data['relationships']['provider']['links']['related']['href'] == \
               f'{settings.API_DOMAIN}v2/providers/registrations/{non_default_provider._id}/'

        draft = DraftRegistration.load(data['id'])
        assert draft.provider == non_default_provider

    # Overrides TestDraftRegistrationList
    def test_cannot_create_draft(
            self, app, user_write_contrib,
            user_read_contrib, user_non_contrib,
            project_public, payload, group,
            url_draft_registrations, group_mem):

        #   test_write_contrib (no node supplied, so any logged in user can create)
        assert user_write_contrib in project_public.contributors.all()
        res = app.post_json_api(
            url_draft_registrations,
            payload,
            auth=user_write_contrib.auth)
        assert res.status_code == 201

    #   test_read_only (no node supplied, so any logged in user can create)
        assert user_read_contrib in project_public.contributors.all()
        res = app.post_json_api(
            url_draft_registrations,
            payload,
            auth=user_read_contrib.auth)
        assert res.status_code == 201

    #   test_non_authenticated_user_cannot_create_draft
        res = app.post_json_api(
            url_draft_registrations,
            payload, expect_errors=True)
        assert res.status_code == 401

    #   test_logged_in_non_contributor (no node supplied, so any logged in user can create)
        res = app.post_json_api(
            url_draft_registrations,
            payload,
            auth=user_non_contrib.auth)
        assert res.status_code == 201

    # Overrides TestDraftRegistrationList
    def test_cannot_create_draft_errors(self):
        # The original test assumes a node is being passed in
        return

    def test_draft_registration_attributes_not_copied_from_node(self, app, project_public,
            url_draft_registrations, user, payload):

        GPL3 = NodeLicense.objects.get(license_id='GPL3')
        project_public.set_node_license(
            {
                'id': GPL3.license_id,
                'year': '1998',
                'copyrightHolders': ['Grapes McGee']
            },
            auth=Auth(user),
            save=True
        )

        res = app.post_json_api(url_draft_registrations, payload, auth=user.auth)
        assert res.status_code == 201
        attributes = res.json['data']['attributes']
        assert attributes['title'] == 'Untitled'
        assert attributes['description'] != project_public.description
        assert attributes['category'] != project_public.category
        assert set(attributes['tags']) != set([tag.name for tag in project_public.tags.all()])
        assert attributes['node_license'] is None

        relationships = res.json['data']['relationships']

        assert 'affiliated_institutions' in relationships
        assert 'subjects' in relationships
        assert 'contributors' in relationships
