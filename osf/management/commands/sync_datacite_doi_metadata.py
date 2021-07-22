#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time

from django.core.management.base import BaseCommand
from osf.models import Registration, Identifier
import logging
from datacite.errors import DataCiteForbiddenError
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)

def retry(func, retries=4):
    for i in range(retries):
        try:
            time.sleep(0.3)
            return func('doi')
        except DataCiteForbiddenError as e:
            if i < 1:
                raise e
            time.sleep(10)

def sync_datacite_doi_metadata(dry_run=True):
    content_type = ContentType.objects.get_for_model(Registration)
    reg_ids = Identifier.objects.filter(category='doi', content_type=content_type, deleted__isnull=True).values_list(
        'object_id',
        flat=True
    )

    registrations = Registration.objects.exclude(id__in=reg_ids, deleted__isnull=False, moderation_state='withdrawn')
    logger.info(f'{registrations.count()} registrations to mint')
    for registration in registrations:
        if not dry_run:
            doi = retry(registration.request_identifier)['doi']
            registration.set_identifier_value('doi', doi)

        logger.info(f'doi minting for {registration._id} complete')


class Command(BaseCommand):
    """Adds DOIs to all registrations"""
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--dry',
            action='store_true',
            dest='dry_run',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        sync_datacite_doi_metadata(dry_run=dry_run)
