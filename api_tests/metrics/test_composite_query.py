import time
import pytest
from datetime import datetime
from osf_tests.factories import (
    PreprintFactory,
    AuthUserFactory
)

from osf.metrics import PreprintDownload
from api.base.settings import API_PRIVATE_BASE as API_BASE
from elasticsearch_dsl import Index


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


@pytest.fixture
def base_url():
    return '/{}metrics/preprints/'.format(API_BASE)

@pytest.mark.django_db
class TestElasticSearch():

    @pytest.fixture(autouse=True)
    def mock_elastic(self, es_client):
        ind = Index('test_osf_preprintdownload_2020')
        ind.save()
        ind.delete()
        ind.save()
        PreprintDownload._index = ind
        PreprintDownload._template_name = 'test_' + PreprintDownload._template_name
        PreprintDownload._template = 'test_' + PreprintDownload._template
        PreprintDownload.sync_index_template()
        ind.save()
        yield
        ind.delete()

    def test_elasticsearch_agg_query(self, app, user, base_url, preprint):
        post_url = '{}downloads/'.format(base_url)

        payload = {
            'data': {
                'type': 'preprint_metrics',
                'attributes': {
                    'query': {
                        'aggs': {
                            'preprints_by_year': {
                                'composite': {
                                    'sources': [{
                                        'date': {
                                            'date_histogram': {
                                                'field': 'timestamp',
                                                'interval': 'year'
                                            }
                                        }
                                    }]
                                }
                            }
                        }
                    }
                }
            }
        }

        resp = app.post_json_api(post_url, payload, auth=user.auth)

        assert resp.status_code == 200
        assert resp.json['hits']['hits'] == []

        pd = PreprintDownload(
            count=1,
            preprint_id=preprint._id,
            user_id=user._id,
            provider_id=preprint.provider._id,
            timestamp=datetime(year=2020, month=1, day=1),
        )
        pd.meta['result'] = 'created'
        pd.save()

        pd = PreprintDownload(
            count=1,
            preprint_id=preprint._id,
            user_id=user._id,
            provider_id=preprint.provider._id,
            timestamp=datetime(year=2020, month=2, day=1),
        )
        pd.meta['result'] = 'created'
        pd.save()

        time.sleep(1)  # gives ES some time to update

        resp = app.post_json_api(post_url, payload, auth=user.auth)
        assert resp.status_code == 200
        assert len(resp.json['aggregations']['preprints_by_year']['buckets']) == 1

        payload['data']['attributes']['query']['aggs']['preprints_by_year']['composite']['sources'][0]['date']['date_histogram']['interval'] = 'month'

        resp = app.post_json_api(post_url, payload, auth=user.auth)
        assert len(resp.json['aggregations']['preprints_by_year']['buckets']) == 2
