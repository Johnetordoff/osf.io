# -*- coding: utf-8 -*-

import furl
import lxml
import time
import datetime
import requests
from framework.exceptions import HTTPError

from website.identifiers.metadata import remove_control_characters
from website.util.client import BaseClient
from website import settings
from datacite import DataCiteMDSClient, errors, schema40

from . import utils


class EzidClient(BaseClient):

    BASE_URL = 'https://ezid.cdlib.org'

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def _build_url(self, *segments, **query):
        url = furl.furl(self.BASE_URL)
        url.path.segments.extend(segments)
        url.args.update(query)
        return url.url

    @property
    def _auth(self):
        return (self.username, self.password)

    @property
    def _default_headers(self):
        return {'Content-Type': 'text/plain; charset=UTF-8'}

    def get_identifier(self, identifier):
        resp = self._make_request(
            'GET',
            self._build_url('id', identifier),
            expects=(200, ),
        )
        return utils.from_anvl(resp.content.strip('\n'))

    def create_identifier(self, identifier, metadata=None):
        resp = self._make_request(
            'PUT',
            self._build_url('id', identifier),
            data=utils.to_anvl(metadata or {}),
            expects=(201, ),
        )
        return utils.from_anvl(resp.content)

    def mint_identifier(self, shoulder, metadata=None):
        resp = self._make_request(
            'POST',
            self._build_url('shoulder', shoulder),
            data=utils.to_anvl(metadata or {}),
            expects=(201, ),
        )
        return utils.from_anvl(resp.content)

    def change_status_identifier(self, status, identifier, metadata=None):
        metadata['_status'] = status
        resp = self._make_request(
            'POST',
            self._build_url('id', identifier),
            data=utils.to_anvl(metadata or {}),
            expects=(200, ),
        )
        return utils.from_anvl(resp.content)


class CrossRefClient(BaseClient):

    BASE_URL = settings.CROSSREF_DEPOSIT_URL

    def build_doi(self, node):
        from osf.models import PreprintService, PreprintProvider

        namespace = settings.EZID_DOI_NAMESPACE
        if isinstance(node, PreprintService):
            doi_prefix = node.provider.doi_prefix
            if not doi_prefix:
                doi_prefix = PreprintProvider.objects.get(_id='osf').doi_prefix
            namespace = doi_prefix
        return settings.DOI_FORMAT.format(namespace=namespace, guid=node._id)

    def build_metadata(self, preprint, **kwargs):
        """Return the crossref metadata XML document for a given preprint as a string for DOI minting purposes

        :param preprint -- the preprint
        """

        doi = self.build_doi(preprint)
        if kwargs.get('status', '') == 'unavailable':
            return ''

        element = lxml.builder.ElementMaker(nsmap={
            None: settings.CROSSREF_NAMESPACE,
            'xsi': settings.XSI},
        )

        head = element.head(
            element.doi_batch_id(preprint._id),
            # TODO -- CrossRef has said they don't care about this field, is this OK?
            element.timestamp('{}'.format(int(time.time()))),
            element.depositor(
                element.depositor_name(settings.CROSSREF_DEPOSITOR_NAME),
                element.email_address(settings.CROSSREF_DEPOSITOR_EMAIL)
            ),
            element.registrant(preprint.provider.name)  # TODO - confirm provider name is desired
        )

        posted_content = element.posted_content(
            element.group_title(preprint.provider.name),
            element.contributors(*self._crossref_format_contributors(element, preprint)),
            element.titles(element.title(preprint.node.title)),
            element.posted_date(*self._format_date_crossref(element, preprint.date_published)),
            element.item_number('osf.io/{}'.format(preprint._id)),
            type='preprint'
        )

        if preprint.node.description:
            posted_content.append(
                element.abstract(element.p(preprint.node.description), xmlns=settings.JATS_NAMESPACE))

        if preprint.license and preprint.license.node_license.url:
            posted_content.append(
                element.program(
                    element.license_ref(preprint.license.node_license.url,
                                        start_date=preprint.date_published.strftime('%Y-%m-%d')),
                    xmlns=settings.CROSSREF_ACCESS_INDICATORS
                )
            )

        if preprint.node.preprint_article_doi:
            posted_content.append(
                element.program(
                    element.related_item(
                        element.intra_work_relation(
                            preprint.node.preprint_article_doi,
                            **{'relationship-type': 'isPreprintOf', 'identifier-type': 'doi'}
                        ),
                        xmlns=settings.CROSSREF_RELATIONS
                    )
                )
            )

        doi_data = [
            element.doi(doi),
            element.resource(settings.DOMAIN + preprint._id)
        ]
        posted_content.append(element.doi_data(*doi_data))

        root = element.doi_batch(
            head,
            element.body(posted_content),
            version=settings.CROSSREF_SCHEMA_VERSION
        )
        # set xsi:schemaLocation
        root.attrib['{%s}schemaLocation' % settings.XSI] = settings.CROSSREF_SCHEMA_LOCATION
        return '<?xml version="1.0" encoding="UTF-8"?>\r\n' \
               + lxml.etree.tostring(root, pretty_print=kwargs.get('pretty_print', True))

    def _crossref_format_contributors(self, element, preprint):
        contributors = []
        for index, contributor in enumerate(preprint.node.visible_contributors):
            if index == 0:
                sequence = 'first'
            else:
                sequence = 'additional'

            person = element.person_name(sequence=sequence, contributor_role='author')
            contributor_given_plus_middle = remove_control_characters(
                ' '.join([contributor.given_name, contributor.middle_names]).strip()
            )
            person.append(element.given_name(contributor_given_plus_middle))
            person.append(element.surname(remove_control_characters(contributor.family_name)))
            if contributor.suffix:
                person.append(element.suffix(remove_control_characters(contributor.suffix)))

            contributors.append(person)

        return contributors

    def _format_date_crossref(self, element, date):
        elements = [
            element.month(date.strftime('%m')),
            element.day(date.strftime('%d')),
            element.year(date.strftime('%Y'))
        ]
        return elements

    def _make_request(self, method, url, **kwargs):
        expects = kwargs.pop('expects', None)
        throws = kwargs.pop('throws', None)

        response = requests.request(method, url, **kwargs)
        if expects and response.status_code not in expects:
            raise throws if throws else HTTPError(response.status_code, message=response.content)

        return response

    def _build_url(self, **query):
        url = furl.furl(self.BASE_URL)
        url.args.update(query)
        return url.url

    def create_identifier(self, doi, metadata):
        filename = doi.split('/')[-1]
        print(metadata)
        res = self._make_request(
            'POST',
            self._build_url(
                operation='doMDUpload',
                login_id=settings.CROSSREF_USERNAME,
                login_passwd=settings.CROSSREF_PASSWORD,
                fname='{}.xml'.format(filename)
            ),
            files={'file': ('{}.xml'.format(filename), metadata)},
            expects=(200, )
        )

        return res

    def change_status_identifier(self, status, identifier, metadata=None):
        return self.create_identifier(identifier, metadata=metadata)


class DataCiteClient(BaseClient):

    BASE_URL = settings.DATACITE_URL
    FORMAT = settings.DATACITE_FORMAT
    DOI_NAMESPACE = settings.DATACITE_DOI_NAMESPACE

    def __init__(self, username, password):
        self.username = username
        self.password = password

    @property
    def _client(self):
        return DataCiteMDSClient(
            url=settings.DATACITE_URL,
            username=settings.DATACITE_USERNAME,
            password=settings.DATACITE_PASSWORD,
            prefix=settings.DATACITE_PREFIX
        )

    def build_doi(self, node):
        return self.FORMAT.format(namespace=self.DOI_NAMESPACE, guid=node._id)

    def build_metadata(self, node):
        """Return the formatted datacite metadata XML as a string.
         """

        data = {
            'identifier': {
                'identifier': self.build_doi(node),
                'identifierType': 'DOI',
            },
            'creators': [
                {'creatorName': user.fullname,
                 'givenName': user.given_name,
                 'familyName': user.family_name} for user in node.contributors
            ],
            'titles': [
                {'title': node.title}
            ],
            'publisher': 'Open Science Framework',
            'publicationYear': str(datetime.datetime.now().year),
            'resourceType': {
                'resourceTypeGeneral': 'Dataset'
            }
        }

        if node.description:
            data['descriptions'] = [{
                'descriptionType': 'Abstract',
                'description': node.description
            }]

        if node.node_license:
            data['rightsList'] = [{
                'rights': node.node_license.name,
                'rightsURI': node.node_license.url
            }]

        # Validate dictionary
        assert schema40.validate(data)

        # Generate DataCite XML from dictionary.
        return schema40.tostring(data)

    def get_identifier(self, identifier):
        self._client.doi_get(identifier)

    def create_identifier(self, doi, metadata):

        try:
            res = self._client.metadata_post(metadata)
        except errors.DataCiteServerError:  # This hangs if uncaught.
            raise HTTPError(code=503, message='Datacite is unavailable.')

        return res

    def change_status_identifier(self, status, identifier, metadata):
        return self.create_identifier(identifier, metadata=metadata)
