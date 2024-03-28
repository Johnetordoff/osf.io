import waffle
from kombu import Exchange
from framework.celery_tasks import app as celery_app
from website import settings
from osf import features


def publish_deactivated_user(user):
    if settings.USE_CELERY and waffle.switch_is_active(features.ENABLE_GV):
        _publish_user_status_change(
            body={
                'action': 'deactivate',
                'user_uri': user.get_semantic_iri(),
            }
        )


def publish_reactivate_user(user):
    if settings.USE_CELERY and waffle.switch_is_active(features.ENABLE_GV):
        _publish_user_status_change(
            body={
                'action': 'reactivate',
                'user_uri': user.get_semantic_iri(),
            },
        )


def publish_merged_user(user):
    assert user.merged_by, 'User received merge signal, but has no `merged_by` reference.'
    if settings.USE_CELERY and waffle.switch_is_active(features.ENABLE_GV):
        _publish_user_status_change(
            body={
                'action': 'merge',
                'into_user_uri': user.merged_by.get_semantic_iri(),
                'from_user_uri': user.get_semantic_iri(),
            },
        )


def _publish_user_status_change(body: dict):
    with celery_app.producer_pool.acquire() as producer:
        producer.publish(
            body=body,
            exchange=Exchange(celery_app.conf.task_account_status_changes_queue),
            serializer='json'
        )
