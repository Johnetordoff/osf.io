"""Resend all resources (nodes, registrations, preprints) for given providers to SHARE."""
import logging

from django.core.management.base import BaseCommand
from osf.models import (
    Collection,
    CollectionSubmission
)
from osf.metadata.serializers.osf_search import OsfSearchMetadataSerializer
from elasticsearch8 import helpers, Elasticsearch

from website import settings
from osf.metadata.rdfutils import OSF

logger = logging.getLogger(__name__)
client = Elasticsearch(settings.ELASTIC_URI)


def gendata(collections):
    actions = []
    for collection in collections:
        actions += [
            {
                '_index': OSF.CollectionSubmission,
                'title': collection_submission.guid.referent.title,
                'description': collection_submission.guid.referent.description,
                'load_pagination_id': collection_submission._id,
            } for collection_submission in collection.active_collection_submissions if collection_submission.index_in_search
        ]

    for action in actions:
        yield action


def reindex_collections():
    client.indices.delete(
        index=OSF.CollectionSubmission,
        ignore=[400]
    )  # HTTP 400 if index already exists
    client.indices.create(
        index=OSF.CollectionSubmission,
        ignore=[400]
    )  # HTTP 400 if index already exists
    client.indices.put_mapping(
        index=OSF.CollectionSubmission,
        body=OsfSearchMetadataSerializer.mappings[OSF.CollectionSubmission],
    )

    collections = Collection.objects.all()
    print('collections', collections)

    helpers.bulk(
        client,
        gendata(collections),
        refresh=True,
        raise_on_error=True
    )


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

    def handle(self, *args, **options):
        reindex_collections()
