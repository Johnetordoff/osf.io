import mock
import pytest
from nose.tools import (
    assert_equal,
    assert_false,
    assert_in,
    assert_true
)

from addons.github.models import GithubFile
from api_tests import utils as test_utils
from api.base.settings.defaults import API_BASE
from osf.models import Preprint, Node
from osf.utils import permissions
from osf_tests.factories import (
    ProjectFactory,
    PreprintFactory,
    AuthUserFactory,
    SubjectFactory,
    PreprintProviderFactory,
)
from tests.base import ApiTestCase, capture_signals
from website.project import signals as project_signals


def build_preprint_update_payload(preprint_id, primary_file_id, is_published=True):
    return {
        'data': {
            'id': preprint_id,
            'type': 'preprints',
            'attributes': {
                'is_published': is_published,
                'subjects': [[SubjectFactory()._id]],
            },
            'relationships': {
                'primary_file': {
                    'data': {
                        'type': 'primary_file',
                        'id': primary_file_id
                    }
                }
            }
        }
    }

def build_preprint_create_payload(node_id=None, provider_id=None, file_id=None, attrs={}):
    attrs['title'] = 'A Study of Coffee and Productivity'
    attrs['description'] = 'The more the better'

    payload = {
        'data': {
            'attributes': attrs,
            'relationships': {},
            'type': 'preprints'
        }
    }
    if node_id:
        payload['data']['relationships']['node'] = {
            'data': {
                'type': 'node',
                'id': node_id
            }
        }
    if provider_id:
        payload['data']['relationships']['provider'] = {
            'data': {
                'type': 'provider',
                'id': provider_id
            }
        }
    if file_id:
        payload['data']['relationships']['primary_file'] = {
            'data': {
                'type': 'primary_file',
                'id': file_id
            }
        }
    return payload

def build_preprint_create_payload_without_node(provider_id=None, file_id=None, attrs=None):
    attrs = attrs or {}
    return build_preprint_create_payload(node_id=None, provider_id=provider_id, file_id=file_id, attrs=attrs)

@pytest.mark.django_db
class TestPreprintCreateWithoutNode:

    @pytest.fixture()
    def user_one(self):
        return AuthUserFactory()

    @pytest.fixture()
    def subject(self):
        return SubjectFactory()

    @pytest.fixture()
    def provider(self):
        return PreprintProviderFactory()

    @pytest.fixture()
    def url(self):
        return '/{}preprints/'.format(API_BASE)

    @pytest.fixture()
    def supplementary_project(self, user_one):
        return ProjectFactory(creator=user_one)

    @pytest.fixture()
    def preprint_payload(self, provider):
        return {
            'data': {
                'type': 'preprints',
                'attributes': {
                    'title': 'Greatest Wrestlemania Moment Vol IX',
                    'description': 'Crush VS Doink the Clown in an epic battle during WrestleMania IX',
                    'public': False,
                },
                'relationships': {
                    'provider': {
                        'data': {
                            'id': provider._id,
                            'type': 'providers'}}}}}

    def test_create_preprint_logged_in(self, app, user_one, url, preprint_payload):
        res = app.post_json_api(url, preprint_payload, auth=user_one.auth, expect_errors=True)

        assert res.status_code == 201
        assert res.json['data']['attributes']['title'] == preprint_payload['data']['attributes']['title']
        assert res.json['data']['attributes']['description'] == preprint_payload['data']['attributes']['description']
        assert res.content_type == 'application/vnd.api+json'

    def test_create_preprint_does_not_create_a_node(self, app, user_one, provider, url, preprint_payload):
        res = app.post_json_api(url, preprint_payload, auth=user_one.auth, expect_errors=True)

        assert res.status_code == 201
        preprint = Preprint.load(res.json['data']['id'])
        assert preprint.node is None
        assert not Node.objects.filter(preprints__guids___id=res.json['data']['id']).exists()

    def test_create_preprint_with_supplementary_node(self, app, user_one, provider, url, preprint_payload, supplementary_project):
        preprint_payload['data']['relationships']['node'] = {
            'data': {
                'id': supplementary_project._id,
                'type': 'nodes'
            }
        }
        res = app.post_json_api(url, preprint_payload, auth=user_one.auth)

        assert res.status_code == 201
        preprint = Preprint.load(res.json['data']['id'])
        assert preprint.node == supplementary_project
        assert Node.objects.filter(preprints__guids___id=res.json['data']['id']).exists()

    def test_create_preprint_with_incorrectly_specified_node(self, app, user_one, provider, url, preprint_payload, supplementary_project):
        preprint_payload['data']['relationships']['node'] = {
            'data': {
                'id': supplementary_project.id,
                'type': 'nodes'
            }
        }
        res = app.post_json_api(url, preprint_payload, auth=user_one.auth, expect_errors=True)

        assert res.status_code == 400
        assert_equal(res.json['errors'][0]['detail'], 'Node not correctly specified.')

@pytest.mark.django_db
class TestPreprintCreate(ApiTestCase):
    def setUp(self):
        super(TestPreprintCreate, self).setUp()
        self.user = AuthUserFactory()
        self.other_user = AuthUserFactory()
        self.private_project = ProjectFactory(creator=self.user)
        self.public_project = ProjectFactory(creator=self.user, is_public=True)
        self.public_project.add_contributor(self.other_user, permissions=permissions.DEFAULT_CONTRIBUTOR_PERMISSIONS, save=True)
        self.subject = SubjectFactory()
        self.provider = PreprintProviderFactory()
        self.user_two = AuthUserFactory()
        self.url = '/{}preprints/'.format(API_BASE)

    def publish_preprint(self, preprint, user, expect_errors=False):
        preprint_file = test_utils.create_test_preprint_file(preprint, user, 'coffee_manuscript.pdf')
        update_payload = build_preprint_update_payload(preprint._id, preprint_file._id)

        res = self.app.patch_json_api(self.url + '{}/'.format(preprint._id), update_payload, auth=user.auth, expect_errors=expect_errors)
        return res

    def test_create_preprint_with_supplemental_public_project(self):
        public_project_payload = build_preprint_create_payload(self.public_project._id, self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.user.auth)

        data = res.json['data']
        preprint = Preprint.load(data['id'])
        assert_equal(res.status_code, 201)
        assert_equal(data['attributes']['is_published'], False)
        assert preprint.node == self.public_project

    def test_create_preprint_with_supplemental_private_project(self):
        private_project_payload = build_preprint_create_payload(self.private_project._id, self.provider._id, attrs={'subjects': [[SubjectFactory()._id]]})
        res = self.app.post_json_api(self.url, private_project_payload, auth=self.user.auth)

        assert_equal(res.status_code, 201)
        self.private_project.reload()
        assert_false(self.private_project.is_public)

        preprint = Preprint.load(res.json['data']['id'])
        res = self.publish_preprint(preprint, self.user)
        preprint.reload()
        assert_equal(res.status_code, 200)
        self.private_project.reload()
        assert_false(self.private_project.is_public)
        assert_true(preprint.is_public)
        assert_true(preprint.is_published)

    def test_non_authorized_user_on_supplemental_node(self):
        public_project_payload = build_preprint_create_payload(self.public_project._id, self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.user_two.auth, expect_errors=True)

        assert_equal(res.status_code, 403)

    def test_write_user_on_supplemental_node(self):
        assert_in(self.other_user, self.public_project.contributors)
        public_project_payload = build_preprint_create_payload(self.public_project._id, self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.other_user.auth, expect_errors=True)
        assert_equal(res.status_code, 201)

    def test_read_user_on_supplemental_node(self):
        self.public_project.set_permissions(self.other_user, permissions.READ, save=True)
        assert_in(self.other_user, self.public_project.contributors)
        public_project_payload = build_preprint_create_payload(self.public_project._id, self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.other_user.auth, expect_errors=True)
        assert_equal(res.status_code, 403)

    def test_file_is_not_in_node(self):
        file_one_project = test_utils.create_test_file(self.public_project, self.user, 'openupthatwindow.pdf')
        assert_equal(file_one_project.target, self.public_project)
        wrong_project_payload = build_preprint_create_payload(self.public_project._id, self.provider._id, file_one_project._id)
        res = self.app.post_json_api(self.url, wrong_project_payload, auth=self.user.auth, expect_errors=True)

        assert_equal(res.status_code, 400)
        assert_equal(res.json['errors'][0]['detail'], 'This file is not a valid primary file for this preprint.')

    def test_already_has_supplemental_node_on_another_preprint(self):
        preprint = PreprintFactory(creator=self.user, project=self.public_project)
        already_preprint_payload = build_preprint_create_payload(preprint.node._id, preprint.provider._id)
        res = self.app.post_json_api(self.url, already_preprint_payload, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, 201)

    def test_read_write_user_already_a_preprint_with_same_provider(self):
        assert_in(self.other_user, self.public_project.contributors)
        preprint = PreprintFactory(creator=self.user, project=self.public_project)
        already_preprint_payload = build_preprint_create_payload(preprint.node._id, preprint.provider._id)
        res = self.app.post_json_api(self.url, already_preprint_payload, auth=self.other_user.auth, expect_errors=True)
        assert_equal(res.status_code, 201)

    def test_publish_preprint_fails_with_no_primary_file(self):
        no_file_payload = build_preprint_create_payload(node_id=self.public_project._id, provider_id=self.provider._id, file_id=None, attrs={'is_published': True, 'subjects': [[SubjectFactory()._id]]})
        res = self.app.post_json_api(self.url, no_file_payload, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, 400)
        assert_equal(res.json['errors'][0]['detail'], 'A valid primary_file must be set before publishing a preprint.')

    def test_publish_preprint_fails_with_invalid_primary_file(self):
        no_file_payload = build_preprint_create_payload(node_id=self.public_project._id, provider_id=self.provider._id, attrs={'subjects': [[SubjectFactory()._id]]})
        res = self.app.post_json_api(self.url, no_file_payload, auth=self.user.auth, expect_errors=True)

        assert_equal(res.status_code, 201)
        preprint = Preprint.load(res.json['data']['id'])
        update_payload = build_preprint_update_payload(preprint._id, 'fakefileid')

        res = self.app.patch_json_api(self.url + '{}/'.format(preprint._id), update_payload, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, 400)
        assert_equal(res.json['errors'][0]['detail'], 'A valid primary_file must be set before publishing a preprint.')

    def test_no_provider_given(self):
        no_providers_payload = build_preprint_create_payload()
        res = self.app.post_json_api(self.url, no_providers_payload, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, 400)
        assert_equal(res.json['errors'][0]['detail'], 'You must specify a valid provider to create a preprint.')

    def test_invalid_provider_given(self):
        wrong_provider_payload = build_preprint_create_payload(provider_id='jobbers')
        res = self.app.post_json_api(self.url, wrong_provider_payload, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, 400)
        assert_equal(res.json['errors'][0]['detail'], 'You must specify a valid provider to create a preprint.')

    def test_file_not_osfstorage(self):
        public_project_payload = build_preprint_create_payload(provider_id=self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.user.auth, expect_errors=True)

        preprint = Preprint.load(res.json['data']['id'])
        assert_equal(res.status_code, 201)

        github_file = test_utils.create_test_preprint_file(preprint, self.user, 'coffee_manuscript.pdf')
        github_file.recast(GithubFile._typedmodels_type)
        github_file.save()

        update_payload = build_preprint_update_payload(preprint._id, github_file._id)
        res = self.app.patch_json_api(self.url + '{}/'.format(preprint._id), update_payload, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, 400)
        assert_equal(res.json['errors'][0]['detail'], 'This file is not a valid primary file for this preprint.')

    def test_preprint_contributor_signal_sent_on_creation(self):
        with capture_signals() as mock_signals:
            payload = build_preprint_create_payload(provider_id=self.provider._id)
            res = self.app.post_json_api(self.url, payload, auth=self.user.auth)

            assert_equal(res.status_code, 201)
            assert_true(len(mock_signals.signals_sent()) == 1)
            assert_in(project_signals.contributor_added, mock_signals.signals_sent())

    def test_create_preprint_with_deleted_node_should_fail(self):
        self.public_project.is_deleted = True
        self.public_project.save()
        public_project_payload = build_preprint_create_payload(self.public_project._id, self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, 400)
        assert_equal(res.json['errors'][0]['detail'], 'Cannot attach a deleted project to a preprint.')

    def test_create_preprint_with_no_permissions_to_node(self):
        project = ProjectFactory()
        public_project_payload = build_preprint_create_payload(project._id, self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.user.auth, expect_errors=True)
        assert_equal(res.status_code, 403)

    def test_create_preprint_adds_log_if_published(self):
        public_project_payload = build_preprint_create_payload(provider_id=self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.user.auth)
        assert_equal(res.status_code, 201)

        preprint = Preprint.load(res.json['data']['id'])
        res = self.publish_preprint(preprint, self.user)

        log = preprint.logs.latest()
        assert_equal(log.action, 'published')
        assert_equal(log.params.get('preprint'), preprint._id)

    @mock.patch('osf.models.preprint.update_or_enqueue_on_preprint_updated')
    def test_create_preprint_from_project_published_hits_update(self, mock_on_preprint_updated):
        private_project_payload = build_preprint_create_payload(self.private_project._id, self.provider._id)
        res = self.app.post_json_api(self.url, private_project_payload, auth=self.user.auth)

        assert_false(mock_on_preprint_updated.called)
        preprint = Preprint.load(res.json['data']['id'])
        self.publish_preprint(preprint, self.user)

        assert_true(mock_on_preprint_updated.called)

    @mock.patch('osf.models.preprint.update_or_enqueue_on_preprint_updated')
    def test_create_preprint_from_project_unpublished_does_not_hit_update(self, mock_on_preprint_updated):
        private_project_payload = build_preprint_create_payload(self.private_project._id, self.provider._id)
        self.app.post_json_api(self.url, private_project_payload, auth=self.user.auth)
        assert not mock_on_preprint_updated.called

    @mock.patch('osf.models.preprint.update_or_enqueue_on_preprint_updated')
    def test_setting_is_published_with_moderated_provider_fails(self, mock_on_preprint_updated):
        self.provider.reviews_workflow = 'pre-moderation'
        self.provider.save()
        public_project_payload = build_preprint_create_payload(self.public_project._id, self.provider._id)
        res = self.app.post_json_api(self.url, public_project_payload, auth=self.user.auth, expect_errors=True)
        assert res.status_code == 201
        preprint = Preprint.load(res.json['data']['id'])
        res = self.publish_preprint(preprint, self.user, expect_errors=True)
        assert res.status_code == 409
        assert not mock_on_preprint_updated.called
