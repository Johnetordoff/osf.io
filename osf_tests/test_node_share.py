import mock
import json

import pytest
import responses

from framework.auth.core import Auth
from framework.sessions import set_session
from website import settings

from website.project.tasks import on_node_updated, format_registration

from osf.models import SpamStatus

from osf_tests.factories import (
    UserFactory,
    NodeFactory,
    SessionFactory,
    ProjectFactory,
    RegistrationFactory,
    RegistrationProviderFactory,
)


@pytest.mark.django_db
@pytest.mark.enable_enqueue_task
class TestSHAREOnNodeUpdate:
    @pytest.fixture(autouse=True)
    def session(self, user, request_context):
        s = SessionFactory(user=user)
        set_session(s)
        return s

    @pytest.fixture(autouse=True)
    def mock_share_settings(self):
        with mock.patch('website.project.tasks.settings.SHARE_API_TOKEN', 'Token'):
            with mock.patch(
                'website.project.tasks.settings.SHARE_URL', 'https://share.osf.io'
            ):
                yield

    @pytest.fixture(autouse=True)
    def mock_share(self):
        responses.add(
            responses.Response(
                responses.POST, 'https://share.osf.io/api/normalizeddata/', status=200,
            )
        )

    @pytest.fixture()
    def do_not_index_tag(self):
        return settings.DO_NOT_INDEX_LIST['tags'][0]

    @pytest.fixture()
    def do_not_index_title(self):
        return settings.DO_NOT_INDEX_LIST['titles'][0]

    @pytest.fixture()
    def user(self):
        return UserFactory()

    @pytest.fixture()
    def node(self):
        return ProjectFactory(is_public=True)

    @pytest.fixture()
    def registration(self, node):
        reg_provider = RegistrationProviderFactory(name='test')
        reg_provider.access_token = 'mock token'
        reg_provider.save()
        registration = RegistrationFactory(is_public=True, provider=reg_provider)
        registration.archive_jobs.clear()
        registration.save()

        return registration

    @pytest.fixture()
    def component_registration(self, node):
        NodeFactory(
            creator=node.creator, parent=node, title='Title1',
        )
        registration = RegistrationFactory(project=node)
        registration.refresh_from_db()
        return registration.get_nodes()[0]

    @responses.activate
    def test_updates_share(self, node, user):
        on_node_updated(node._id, user._id, False, {'is_public'})
        data = json.loads(responses.calls[0].request.body)
        graph = data['data']['attributes']['data']['@graph']

        assert responses.calls[0].request.headers['Authorization'] == 'Bearer Token'
        assert graph[0]['uri'] == f'{settings.DOMAIN}{node._id}/'

    @responses.activate
    def test_on_node_updated_status(self, node, user):

        cases = [
            {
                'is_deleted': False,
                'attrs': {
                    'is_public': True,
                    'is_deleted': False,
                    'spam_status': SpamStatus.HAM,
                },
            },
            {
                'is_deleted': True,
                'attrs': {
                    'is_public': False,
                    'is_deleted': False,
                    'spam_status': SpamStatus.HAM,
                },
            },
            {
                'is_deleted': True,
                'attrs': {
                    'is_public': True,
                    'is_deleted': True,
                    'spam_status': SpamStatus.HAM,
                },
            },
            {
                'is_deleted': True,
                'attrs': {
                    'is_public': True,
                    'is_deleted': False,
                    'spam_status': SpamStatus.SPAM,
                },
            },
        ]

        for i, case in enumerate(cases):
            for attr, value in case['attrs'].items():
                setattr(node, attr, value)
            node.save()

            on_node_updated(node._id, user._id, False, {'is_public'})

            data = json.loads(responses.calls[i].request.body)
            graph = data['data']['attributes']['data']['@graph']
            assert graph[1]['is_deleted'] == case['is_deleted']

    @responses.activate
    def test_update_share_registrations(self, registration, user):

        cases = [
            {'is_deleted': False, 'attrs': {'is_public': True, 'is_deleted': False}},
            {'is_deleted': True, 'attrs': {'is_public': False, 'is_deleted': False}},
            {'is_deleted': True, 'attrs': {'is_public': True, 'is_deleted': True}},
            {'is_deleted': False, 'attrs': {'is_public': True, 'is_deleted': False}},
        ]

        for i, case in enumerate(cases):
            for attr, value in case['attrs'].items():
                setattr(registration, attr, value)
            registration.save()

            on_node_updated(registration._id, user._id, False, {'is_public'})

            assert registration.is_registration
            data = json.loads(responses.calls[i].request.body)
            graph = data['data']['attributes']['data']['@graph']
            payload = next((item for item in graph if 'is_deleted' in item.keys()))
            assert payload['is_deleted'] == case['is_deleted']

    @responses.activate
    def test_dont_update_share_with_qa_tags(self, node, user, do_not_index_tag):
        node.add_tag(do_not_index_tag, auth=Auth(user))
        on_node_updated(node._id, user._id, False, {'is_public'})

        data = json.loads(responses.calls[0].request.body)
        graph = data['data']['attributes']['data']['@graph']
        payload = next((item for item in graph if 'is_deleted' in item.keys()))
        assert payload['is_deleted'] is True

        node.remove_tag(
            settings.DO_NOT_INDEX_LIST['tags'][0], auth=Auth(user), save=True
        )
        on_node_updated(node._id, user._id, False, {'is_public'})

        data = json.loads(responses.calls[3].request.body)
        graph = data['data']['attributes']['data']['@graph']
        payload = next((item for item in graph if 'is_deleted' in item.keys()))
        assert payload['is_deleted'] is False

    @responses.activate
    def test_dont_update_share_with_qa_tags_registrations(
        self, registration, user, do_not_index_tag
    ):
        registration.add_tag(do_not_index_tag, auth=Auth(user))
        on_node_updated(registration._id, user._id, False, {'is_public'})
        data = json.loads(responses.calls[0].request.body)
        graph = data['data']['attributes']['data']['@graph']
        payload = next((item for item in graph if 'is_deleted' in item.keys()))
        assert payload['is_deleted'] is True

        registration.remove_tag(do_not_index_tag, auth=Auth(user), save=True)
        on_node_updated(registration._id, user._id, False, {'is_public'})
        data = json.loads(responses.calls[3].request.body)
        graph = data['data']['attributes']['data']['@graph']
        payload = next((item for item in graph if 'is_deleted' in item.keys()))
        assert payload['is_deleted'] is False

    @responses.activate
    def test_update_share_correctly_for_projects_with_qa_titles(
        self, node, user, do_not_index_title
    ):
        node.title = do_not_index_title
        node.save()
        on_node_updated(node._id, user._id, False, {'is_public'})
        data = json.loads(responses.calls[0].request.body)
        graph = data['data']['attributes']['data']['@graph']
        payload = next((item for item in graph if 'is_deleted' in item.keys()))
        assert payload['is_deleted'] is True

        node.title = 'Not a qa title'
        node.save()
        assert node.title not in settings.DO_NOT_INDEX_LIST['titles']
        on_node_updated(node._id, user._id, False, {'is_public'})
        data = json.loads(responses.calls[1].request.body)
        graph = data['data']['attributes']['data']['@graph']
        payload = next((item for item in graph if 'is_deleted' in item.keys()))
        assert payload['is_deleted'] is False

    @responses.activate
    def test_update_share_correctly_for_registrations_with_qa_titles(
        self, registration, user, do_not_index_title
    ):
        registration.title = do_not_index_title
        registration.save()

        on_node_updated(registration._id, user._id, False, {'is_public'})
        data = json.loads(responses.calls[0].request.body)
        graph = data['data']['attributes']['data']['@graph']
        payload = next((item for item in graph if 'is_deleted' in item.keys()))
        assert payload['is_deleted'] is True

        registration.title = 'Not a qa title'
        registration.save()
        assert registration.title not in settings.DO_NOT_INDEX_LIST['titles']
        on_node_updated(registration._id, user._id, False, {'is_public'})
        data = json.loads(responses.calls[1].request.body)
        graph = data['data']['attributes']['data']['@graph']
        payload = next((item for item in graph if 'is_deleted' in item.keys()))
        assert payload['is_deleted'] is False

    @responses.activate
    @mock.patch('website.project.tasks.settings.SHARE_URL', None)
    @mock.patch('website.project.tasks.settings.SHARE_API_TOKEN', None)
    def test_skips_no_settings(self, node, user):
        on_node_updated(node._id, user._id, False, {'is_public'})
        assert len(responses.calls) == 0

    @responses.activate
    @mock.patch('website.project.tasks.settings.SHARE_URL', 'http://a_real_url.old')
    @mock.patch('website.project.tasks._async_update_node_share.delay')
    def test_call_async_update_on_500_failure(self, mock_async, node, user):
        responses.add(
            responses.Response(
                responses.POST, 'http://a_real_url.old/api/normalizeddata/', status=501
            )
        )

        on_node_updated(node._id, user._id, False, {'is_public'})
        assert mock_async.called

    @responses.activate
    @mock.patch('website.project.tasks.settings.SHARE_URL', 'http://a_real_url.old')
    @mock.patch('website.project.tasks.send_desk_share_error')
    @mock.patch('website.project.tasks._async_update_node_share.delay')
    def test_no_call_async_update_on_400_failure(
        self, mock_async, mock_mail, node, user
    ):
        responses.add(
            responses.Response(
                responses.POST, 'http://a_real_url.old/api/normalizeddata/', status=400
            )
        )

        on_node_updated(node._id, user._id, False, {'is_public'})
        assert mock_mail.called
        assert not mock_async.called

    def test_format_registration_gets_parent_hierarchy_for_component_registrations(
        self, component_registration
    ):

        graph = format_registration(component_registration)

        parent_relation = [i for i in graph if i['@type'] == 'ispartof'][0]
        parent_work_identifier = [
            i
            for i in graph
            if 'creative_work' in i
            and i['creative_work']['@id'] == parent_relation['subject']['@id']
        ][0]

        # Both must exist to be valid
        assert parent_relation
        assert parent_work_identifier

    @responses.activate
    def test_registation_provider_sends_token(self, registration, user):
        """
        This test ensures when a registration has a provider that providers token is sent to SHARE instead of the OSF's
        whole-site token.
        :param registration:
        :param user:
        :param request_context:
        :return:
        """
        on_node_updated(registration._id, user._id, False, {'is_public'})
        token = responses.calls[0].request.headers['Authorization'].lstrip('Bearer ')

        assert registration.provider.access_token == token
