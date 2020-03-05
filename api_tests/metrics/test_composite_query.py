import pytest

from osf_tests.factories import (
    PreprintFactory,
    AuthUserFactory
)

from osf.metrics import PreprintDownload
from elasticsearch_dsl import Index
from api.base.settings import API_PRIVATE_BASE as API_BASE


@pytest.fixture()
def preprint():
    return PreprintFactory()


@pytest.fixture()
def user():
    user = AuthUserFactory()
    user.is_staff = True
    user.add_system_tag('preprint_metrics')
    user.save()
    return user


TEST_INDEX = 'test'


@pytest.fixture()
def elastic_mock():
    index = Index(f'{TEST_INDEX}_2020')
    index.delete()
    index.save()
    PreprintDownload._template = f'{TEST_INDEX}_2020'
    PreprintDownload._template_name = TEST_INDEX

@pytest.fixture
def base_url():
    return '/{}metrics/preprints/'.format(API_BASE)

@pytest.mark.django_db
class TestElasticSearch():

    def test_elasticsearch(self, preprint, user, elastic_mock):

        assert PreprintDownload.search().execute().hits == []

        pp = PreprintDownload.record_for_preprint(
            preprint,
            user
        )
        pp.save()

        # wait until ES records the hit
        while not PreprintDownload.search().execute().hits:
            pass

        hit = PreprintDownload.search().execute().hits[0]

        assert hit.preprint_id == preprint._id

    def test_elasticsearch_agg_query(self, app, user, base_url):
        """
        """
        post_url = '{}downloads/'.format(base_url)

        query = {'aggs': {'random_words': {
            'composite': {'sources': [{'date': {'date_histogram': {'field': 'timestamp', 'interval': 'week'}}}]}}}}

        payload = {'data': {'type': 'preprint_metrics', 'attributes': {'query': query}}}

        resp = app.post_json_api(post_url, payload, auth=user.auth)

        assert resp.status_code == 200

        print(resp.__dict__)
