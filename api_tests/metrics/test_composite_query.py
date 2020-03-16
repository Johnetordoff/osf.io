import time
import pytest
from datetime import datetime
from osf_tests.factories import (
    PreprintFactory,
    AuthUserFactory
)

from osf.metrics import PreprintDownload
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


@pytest.fixture
def base_url():
    return '/{}metrics/preprints/'.format(API_BASE)

@pytest.mark.django_db
class TestElasticSearch():

    @pytest.mark.es
    def test_elasticsearch_agg_query(self, app, user, base_url, preprint, es_client):

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
        pd.save()

        pd = PreprintDownload(
            count=1,
            preprint_id=preprint._id,
            user_id=user._id,
            provider_id=preprint.provider._id,
            timestamp=datetime(year=2020, month=2, day=1),
        )
        pd.save()

        time.sleep(2)  # gives ES some time to update

        resp = app.post_json_api(post_url, payload, auth=user.auth)
        assert resp.status_code == 200
        assert len(resp.json['aggregations']['preprints_by_year']['buckets']) == 1

        payload['data']['attributes']['query']['aggs']['preprints_by_year']['composite']['sources'][0]['date']['date_histogram']['interval'] = 'month'

        resp = app.post_json_api(post_url, payload, auth=user.auth)
        assert len(resp.json['aggregations']['preprints_by_year']['buckets']) == 2
