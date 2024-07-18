import pytest
from django.utils import timezone
from osf_tests.factories import PreprintFactory, AuthUserFactory, ProjectFactory
from api.base.settings.defaults import API_BASE
from website.settings import DOI_FORMAT

@pytest.fixture()
def user():
    return AuthUserFactory()

@pytest.mark.django_db
class TestPreprintDetail:

    @pytest.fixture()
    def preprint(self, user):
        return PreprintFactory(creator=user)

    @pytest.fixture()
    def preprint_pre_mod(self, user):
        return PreprintFactory(reviews_workflow='pre-moderation', is_published=False, creator=user)

    @pytest.fixture()
    def moderator(self, preprint_pre_mod):
        mod = AuthUserFactory()
        preprint_pre_mod.provider.get_group('moderator').user_set.add(mod)
        return mod

    @pytest.fixture()
    def unpublished_preprint(self, user):
        return PreprintFactory(creator=user, is_published=False)

    @pytest.fixture()
    def url(self, preprint):
        return f'/{API_BASE}preprints/{preprint._id}/'

    @pytest.fixture()
    def unpublished_url(self, unpublished_preprint):
        return f'/{API_BASE}preprints/{unpublished_preprint._id}/'

    @pytest.fixture()
    def res(self, app, url):
        return app.get(url)

    @pytest.fixture()
    def data(self, res):
        return res.json['data']

    def test_preprint_detail(self, app, user, preprint, url, res, data):
        assert res.status_code == 200
        assert res.content_type == 'application/vnd.api+json'
        assert data['type'] == 'preprints'
        assert data['id'] == preprint._id
        assert data['attributes']['title'] == preprint.title
        assert data['relationships'].get('contributors', None)
        assert data['relationships']['contributors'].get('data', None) is None
        assert data['relationships']['node'].get('data', None) is None

        deleted_node = ProjectFactory(creator=user, is_deleted=True)
        deleted_preprint = PreprintFactory(project=deleted_node, creator=user)
        deleted_preprint_url = '/{}preprints/{}/'.format(API_BASE, deleted_preprint._id)
        deleted_preprint_res = app.get(deleted_preprint_url, expect_errors=True)
        assert deleted_preprint_res.status_code == 200

        node = ProjectFactory(creator=user)
        preprint_with_node = PreprintFactory(project=node, creator=user)
        preprint_with_node_url = '/{}preprints/{}/'.format(API_BASE, preprint_with_node._id)
        preprint_with_node_res = app.get(preprint_with_node_url)
        node_data = preprint_with_node_res.json['data']['relationships']['node']['data']
        assert node_data.get('id', None) == preprint_with_node.node._id
        assert node_data.get('type', None) == 'nodes'

    def test_withdrawn_preprint(self, app, user, moderator, preprint_pre_mod):
        url = f'/{API_BASE}preprints/{preprint_pre_mod._id}/'
        res = app.get(url, auth=user.auth)
        data = res.json['data']
        assert not data['attributes']['date_withdrawn']
        assert 'withdrawal_justification' not in data['attributes']
        assert 'ever_public' not in data['attributes']

        assert not preprint_pre_mod.ever_public
        preprint_pre_mod.date_withdrawn = timezone.now()
        preprint_pre_mod.withdrawal_justification = 'assumptions no longer apply'
        preprint_pre_mod.save()
        assert preprint_pre_mod.is_retracted
        res = app.get(url, expect_errors=True)
        assert res.status_code == 404
        res = app.get(url, auth=user.auth, expect_errors=True)
        assert res.status_code == 404
        res = app.get(url, auth=moderator.auth)
        assert res.status_code == 200

        preprint_pre_mod.ever_public = True
        preprint_pre_mod.save()
        res = app.get(url, auth=user.auth)
        data = res.json['data']
        assert data['attributes']['date_withdrawn']
        assert 'withdrawal_justification' in data['attributes']
        assert 'assumptions no longer apply' == data['attributes']['withdrawal_justification']
        assert 'date_withdrawn' in data['attributes']

    def test_embed_contributors(self, app, user, preprint):
        url = '/{}preprints/{}/?embed=contributors'.format(API_BASE, preprint._id)
        res = app.get(url, auth=user.auth)
        embeds = res.json['data']['embeds']
        ids = preprint.contributors.all().values_list('guids___id', flat=True)
        ids = [f'{preprint._id}-{id_}' for id_ in ids]
        for contrib in embeds['contributors']['data']:
            assert contrib['id'] in ids

    def test_preprint_doi_link_absent_in_unpublished_preprints(self, app, user, unpublished_preprint, unpublished_url):
        res = app.get(unpublished_url, auth=user.auth)
        assert res.json['data']['id'] == unpublished_preprint._id
        assert res.json['data']['attributes']['is_published'] is False
        assert 'preprint_doi' not in res.json['data']['links'].keys()
        assert res.json['data']['attributes']['preprint_doi_created'] is None

    def test_published_preprint_doi_link_not_returned_before_doi_request(self, app, user, unpublished_preprint, unpublished_url):
        unpublished_preprint.is_published = True
        unpublished_preprint.date_published = timezone.now()
        unpublished_preprint.save()
        res = app.get(unpublished_url, auth=user.auth)
        assert res.json['data']['id'] == unpublished_preprint._id
        assert res.json['data']['attributes']['is_published'] is True
        assert 'preprint_doi' not in res.json['data']['links'].keys()

    def test_published_preprint_doi_link_returned_after_doi_request(self, app, user, preprint, url):
        expected_doi = DOI_FORMAT.format(prefix=preprint.provider.doi_prefix, guid=preprint._id)
        preprint.set_identifier_values(doi=expected_doi)
        res = app.get(url, auth=user.auth)
        assert res.json['data']['id'] == preprint._id
        assert res.json['data']['attributes']['is_published'] is True
        assert 'preprint_doi' in res.json['data']['links'].keys()
        assert res.json['data']['links']['preprint_doi'] == 'https://doi.org/{}'.format(expected_doi)
        assert res.json['data']['attributes']['preprint_doi_created']

    def test_preprint_embed_identifiers(self, app, user, preprint, url):
        embed_url = url + '?embed=identifiers'
        res = app.get(embed_url)
        assert res.status_code == 200
        link = res.json['data']['relationships']['identifiers']['links']['related']['href']
        assert f'{url}identifiers/' in link
