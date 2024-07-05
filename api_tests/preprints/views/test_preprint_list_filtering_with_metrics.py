import mock
import pytest
import datetime as dt
from api.base.settings.defaults import API_BASE
from osf_tests.factories import PreprintFactory
from django.utils import timezone
from osf import features
from waffle.testutils import override_switch


@pytest.mark.django_db
class TestPreprintListWithMetrics:

    @pytest.fixture(autouse=True)
    def enable_elasticsearch_metrics(self):
        with override_switch(features.ELASTICSEARCH_METRICS, active=True):
            yield

    @pytest.mark.parametrize(('metric_name', 'metric_class_name'), [('downloads', 'PreprintDownload'), ('views', 'PreprintView')])
    def test_preprint_list_with_metrics(self, app, metric_name, metric_class_name):
        url = '/{}preprints/?metrics[{}]=total'.format(API_BASE, metric_name)
        preprint1 = PreprintFactory()
        preprint1.downloads = 41
        preprint2 = PreprintFactory()
        preprint2.downloads = 42

        with mock.patch('api.preprints.views.{}.get_top_by_count'.format(metric_class_name)) as mock_get_top_by_count:
            mock_get_top_by_count.return_value = [preprint2, preprint1]
            res = app.get(url)
        assert res.status_code == 200

        preprint_2_data = res.json['data'][0]
        assert preprint_2_data['meta']['metrics']['downloads'] == 42

        preprint_1_data = res.json['data'][1]
        assert preprint_1_data['meta']['metrics']['downloads'] == 41

    @mock.patch('django.utils.timezone.now')
    @pytest.mark.parametrize(('query_value', 'timedelta'), [('daily', dt.timedelta(days=1)), ('weekly', dt.timedelta(days=7)), ('yearly', dt.timedelta(days=365))])
    def test_preprint_list_filter_metric_by_time_period(self, mock_timezone_now, app, settings, query_value, timedelta):
        url = '/{}preprints/?metrics[views]={}'.format(API_BASE, query_value)
        mock_now = dt.datetime.utcnow().replace(tzinfo=timezone.utc)
        mock_timezone_now.return_value = mock_now

        preprint1 = PreprintFactory()
        preprint1.views = 41
        preprint2 = PreprintFactory()
        preprint2.views = 42

        with mock.patch('api.preprints.views.PreprintView.get_top_by_count') as mock_get_top_by_count:
            mock_get_top_by_count.return_value = [preprint2, preprint1]
            res = app.get(url)

        assert res.status_code == 200
        call_kwargs = mock_get_top_by_count.call_args[1]
        assert call_kwargs['after'] == mock_now - timedelta
