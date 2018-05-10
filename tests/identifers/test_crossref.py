# -*- coding: utf-8 -*-
import mock
import responses
from nose.tools import *  # noqa

import pytest

from osf_tests.factories import AuthUserFactory
from osf_tests.factories import RegistrationFactory
from osf_tests.factories import PreprintFactory, PreprintProviderFactory


import lxml.etree

from website import settings
from website.identifiers.client import CrossRefClient
from osf.models import NodeLicense

@pytest.fixture()
def client():
    return CrossRefClient()

@pytest.fixture()
def preprint():
    user = AuthUserFactory()
    node = RegistrationFactory(creator=user)
    license_details = {
        'id': license.license_id,
        'year': '2017',
        'copyrightHolders': ['Jeff Hardy', 'Matt Hardy']
    }

    preprint = PreprintFactory(provider=provider, project=node, is_published=True,
                               license_details=license_details)

    return PreprintFactory(provider=provider)


@pytest.fixture()
def mock_crossref_response():
    return """
        \n\n\n\n<html>\n<head><title>SUCCESS</title>\n</head>\n<body>\n<h2>SUCCESS</h2>\n<p>
        Your batch submission was successfully received.</p>\n</body>\n</html>\n
        """

@pytest.mark.django_db
class TestCrossRefClient:

    @responses.activate
    @mock.patch('website.settings.CROSSREF_USERNAME', 'thisisatest')
    @mock.patch('website.settings.CROSSREF_PASSWORD', 'thisisatest')
    @mock.patch('website.identifiers.client.CrossRefClient.BASE_URL', 'https://test.test.osf.io')
    def test_crossref_create_identifiers(self, client, preprint, mock_crossref_response):
        responses.add(
            responses.Response(
                responses.POST,
                'https://test.test.osf.io',
                body=mock_crossref_response,
                content_type='text/html;charset=ISO-8859-1',
                status=200
            )
        )
        doi = client.build_doi(preprint)
        metadata = client.build_metadata(preprint)

        res = client.create_identifier(doi=doi, metadata=metadata)

        assert res.status_code == 200
        assert 'SUCCESS' in res.content

    @responses.activate
    @mock.patch('website.settings.CROSSREF_USERNAME', 'thisisatest')
    @mock.patch('website.settings.CROSSREF_PASSWORD', 'thisisatest')
    @mock.patch('website.identifiers.client.CrossRefClient.BASE_URL', 'https://test.test.osf.io')
    def test_crossref_change_status_identifier(self,  client, preprint, mock_crossref_response):
        responses.add(
            responses.Response(
                responses.POST,
                'https://test.test.osf.io',
                body=mock_crossref_response,
                content_type='text/html;charset=ISO-8859-1',
                status=200
            )
        )
        doi = client.build_doi(preprint)
        metadata = client.build_metadata(preprint)
        res = client.change_status_identifier(status=None, doi=doi, metadata=metadata)

        assert res.status_code == 200
        assert 'SUCCESS' in res.content

    @mock.patch('website.settings.CROSSREF_USERNAME', 'thisisatest')
    @mock.patch('website.settings.CROSSREF_PASSWORD', 'thisisatest')
    def test_crossref_build_doi(self, client, preprint):
        doi_prefix = preprint.provider.doi_prefix

        assert client.build_doi(preprint) == '{}/FK2osf.io/{}'.format(doi_prefix, preprint._id)


    @mock.patch('website.settings.CROSSREF_USERNAME', 'thisisatest')
    @mock.patch('website.settings.CROSSREF_PASSWORD', 'thisisatest')
    def test_crossref_build_metadata(self, preprint):
        license = NodeLicense.objects.get(name="CC-By Attribution 4.0 International")
        test_email = 'test-email'
        doi = settings.DOI_FORMAT.format(namespace=preprint.provider.doi_prefix, guid=preprint._id)
        with mock.patch('website.settings.CROSSREF_DEPOSITOR_EMAIL', test_email):
            crossref_xml = CrossRefClient().build_metadata(preprint, pretty_print=True)
        root = lxml.etree.fromstring(crossref_xml)

        # header
        assert root.find('.//{%s}doi_batch_id' % settings.CROSSREF_NAMESPACE).text == preprint._id
        assert root.find('.//{%s}depositor_name' % settings.CROSSREF_NAMESPACE).text == settings.CROSSREF_DEPOSITOR_NAME
        assert root.find('.//{%s}email_address' % settings.CROSSREF_NAMESPACE).text == test_email

        # body
        contributors = root.find(".//{%s}contributors" % settings.CROSSREF_NAMESPACE)
        assert len(contributors.getchildren()) == len(preprint.node.visible_contributors)

        assert root.find(".//{%s}group_title" % settings.CROSSREF_NAMESPACE).text == preprint.provider.name
        assert root.find('.//{%s}title' % settings.CROSSREF_NAMESPACE).text == preprint.node.title
        assert root.find('.//{%s}item_number' % settings.CROSSREF_NAMESPACE).text == 'osf.io/{}'.format(preprint._id)
        assert root.find('.//{%s}abstract/' % settings.JATS_NAMESPACE).text == preprint.node.description
        assert root.find('.//{%s}license_ref' % settings.CROSSREF_ACCESS_INDICATORS).text == license.url
        assert root.find('.//{%s}license_ref' % settings.CROSSREF_ACCESS_INDICATORS).get('start_date') == preprint.date_published.strftime('%Y-%m-%d')

        assert root.find('.//{%s}intra_work_relation' % settings.CROSSREF_RELATIONS).text == preprint.node.preprint_article_doi
        assert root.find('.//{%s}doi' % settings.CROSSREF_NAMESPACE).text == settings.DOI_FORMAT.format(namespace=preprint.provider.doi_prefix, guid=preprint._id)
        assert root.find('.//{%s}resource' % settings.CROSSREF_NAMESPACE).text == settings.DOMAIN + preprint._id

        metadata_date_parts = [elem.text for elem in root.find('.//{%s}posted_date' % settings.CROSSREF_NAMESPACE)]
        preprint_date_parts = preprint.date_published.strftime('%Y-%m-%d').split('-')
        assert set(metadata_date_parts) == set(preprint_date_parts)

