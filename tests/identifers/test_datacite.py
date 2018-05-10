import mock
import pytest


@pytest.mark.django_db
class TestDataCiteClient:

    @mock.patch('website.settings.DATACITE_USERNAME', 'thisisatest')
    @mock.patch('website.settings.DATACITE_PASSWORD', 'thisisatest')
    def test_datacite_create_identifiers(self, mock_crossref_response):
        pass

    @mock.patch('website.settings.DATACITE_USERNAME', 'thisisatest')
    @mock.patch('website.settings.DATACITE_PASSWORD', 'thisisatest')
    def test_datacite_change_status_identifier(self, mock_crossref_response):
        pass

    @mock.patch('website.settings.DATACITE_USERNAME', 'thisisatest')
    @mock.patch('website.settings.DATACITE_PASSWORD', 'thisisatest')
    def test_datacite_build_doi(self):
        pass

    @mock.patch('website.settings.DATACITE_USERNAME', 'thisisatest')
    @mock.patch('website.settings.DATACITE_PASSWORD', 'thisisatest')
    def test_crossref_build_metadata(self):
        pass