import json
from osf.metadata import gather
from osf.metadata.rdfutils import (
    DCT,
    DOI,
    FOAF,
    ORCID,
    OSF,
    OWL,
    ROR,
    primitivify_rdf,
)
from osf.metadata.serializers import _base


class OsfSearchMetadataSerializer(_base.MetadataSerializer):
    mediatype = 'application/json'

    mappings = {
        OSF.CollectionSubmission: {
            'properties': {
                'load_pagination_id': {
                    'type': 'text',
                },
                'title': {
                    'type': 'text',
                },
                'description': {
                    'type': 'text',
                },
            }
        }
    }

    def filename(self, osfguid: str):
        return f'{osfguid}-osf-search-metadata.json'

    def serialize(self, basket: gather.Basket):
        metadata = {
        }
        return metadata
