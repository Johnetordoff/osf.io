import pytest
from osf_tests.factories import (
    AuthUserFactory,
    PreprintFactory,
    ProjectFactory,
    InstitutionFactory
)
from tests.base import ApiTestCase
from api.base.settings.defaults import API_BASE
from django.utils import timezone
from nose.tools import (
    assert_equal,
)


@pytest.mark.django_db
class TestPreprintList(ApiTestCase):

    def setUp(self):
        super().setUp()
        self.user = AuthUserFactory()
        self.preprint = PreprintFactory(creator=self.user)
        self.url = f'/{API_BASE}preprints/'

        self.project = ProjectFactory(creator=self.user)
        self.institution = InstitutionFactory()

    def test_return_preprints_logged_out(self):
        res = self.app.get(self.url)
        assert len(res.json['data']) == 1
        assert res.status_code == 200
        assert res.status_code == 200
        assert res.content_type == 'application/vnd.api+json'

    def test_exclude_nodes_from_preprints_endpoint(self):
        res = self.app.get(self.url, auth=self.user.auth)
        ids = [each['id'] for each in res.json['data']]
        assert self.preprint._id in ids
        assert self.project._id not in ids

    def test_withdrawn_preprints_list(self):
        pp = PreprintFactory(reviews_workflow='pre-moderation', is_published=False, creator=self.user)
        pp.machine_state = 'pending'
        mod = AuthUserFactory()
        pp.provider.get_group('moderator').user_set.add(mod)
        pp.date_withdrawn = timezone.now()
        pp.save()

        assert not pp.ever_public  # Sanity check

        unauth_res = self.app.get(self.url)
        user_res = self.app.get(self.url, auth=self.user.auth)
        mod_res = self.app.get(self.url, auth=mod.auth)
        unauth_res_ids = [each['id'] for each in unauth_res.json['data']]
        user_res_ids = [each['id'] for each in user_res.json['data']]
        mod_res_ids = [each['id'] for each in mod_res.json['data']]
        assert pp._id not in unauth_res_ids
        assert pp._id not in user_res_ids
        assert pp._id in mod_res_ids

    def test_return_affiliated_institutions(self):
        """
        Confirmation test for the the new preprint affiliated institutions feature
        """
        self.preprint.affiliated_institutions.add(self.institution)
        res = self.app.get(self.url)
        assert_equal(len(res.json['data']), 1)
        assert_equal(res.status_code, 200)
        assert_equal(res.content_type, 'application/vnd.api+json')
        relationship_link = res.json['data'][0]['relationships']['affiliated_institutions']['links']['href']
        assert f'/v2/preprints/{self.preprint._id}/institutions/' in relationship_link
