from django.apps import apps
import logging
from framework.celery_tasks import app as celery_app
from elasticsearch2 import Elasticsearch
from osf.metadata.osf_gathering import pls_gather_item_metadata


from osf.metadata.serializers import TurtleMetadataSerializer
from website import settings

logger = logging.getLogger(__name__)


@celery_app.task(max_retries=5, default_retry_delay=60)
def update_share_collection(collection_id):
    Collection = apps.get_model('osf.Collection')
    collection = Collection.load(collection_id)
    collection_submissions = collection.collectionsubmission_set.all()

    for collection_submission in collection_submissions:
        obj = collection_submission.guid.referent
        client = Elasticsearch(
            settings.ELASTIC_URI,
            request_timeout=settings.ELASTIC_TIMEOUT,
            retry_on_timeout=True,
            **settings.ELASTIC_KWARGS,
        )

        if obj.is_public or obj.deleted:
            client.delete(
                index=settings.ELASTIC_INDEX,
                doc_type='collectionSubmission',
                id=collection_submission._id,
                refresh=True,
                ignore=[404],
            )
        else:
            body = TurtleMetadataSerializer().serialize(
                pls_gather_item_metadata(collection_submission)
            )

            client.index(
                index=settings.ELASTIC_INDEX,
                doc_type='collectionSubmission',
                body=body,
                id=collection_submission._id,
                refresh=True,
            )
