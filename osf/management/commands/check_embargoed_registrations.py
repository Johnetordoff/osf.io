import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from framework.celery_tasks import app as celery_app

from osf.models import Embargo, Registration

from website import settings


logger = logging.getLogger(__name__)


@celery_app.task(
    ignore_results=False,
    max_retries=5,
    default_retry_delay=60,
    name='osf.management.commands.check_embargoed_registrations'
)
def check_embargoed_registrations(dry_run=False):
    ''' '''
    for embargo in Embargo.objects.filter(state=Embargo.UNAPPROVED):
        if should_be_embargoed(embargo):
            parent_registration = Registration.objects.get(embargo=embargo)
            if parent_registration.is_deleted:
                # Clean up any registration failures during archiving
                embargo.forcibly_reject()
                embargo.save()
                continue

            # Call 'accept' trigger directly. This will terminate the embargo
            # if the registration is unmoderated or push it into the moderation
            # queue if it is part of a moderated registry.
            embargo.accept()

    for embargo in Embargo.objects.filter(state=Embargo.APPROVED):
        if embargo.end_date < timezone.now() and not embargo.is_deleted:
            parent_registration = Registration.objects.get(embargo=embargo)
            if parent_registration.is_deleted:
                # Clean up any registration failures during archiving
                embargo.forcibly_reject()
                embargo.save()
            parent_registration.terminate_embargo()


def should_be_embargoed(embargo):
    """Returns true if embargo was initiated more than 48 hours prior."""
    return (timezone.now() - embargo.initiation_date) >= settings.EMBARGO_PENDING_TIME and not embargo.is_deleted


class Command(BaseCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--dry',
            action='store_true',
            dest='dry_run',
            help='Dry run',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        check_embargoed_registrations(dry_run=dry_run)
