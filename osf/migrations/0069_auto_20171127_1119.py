# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-27 17:19

import logging

from django.db import migrations
from osf.utils.migrations import disable_auto_now_fields

logger = logging.getLogger(__name__)

def add_preprint_doi_created(state, schema):
    """
    Sets preprint_doi_created equal to date_published for existing published preprints.
    """
    PreprintService = state.get_model('osf', 'preprintservice')
    null_preprint_doi_created = PreprintService.objects.filter(preprint_doi_created__isnull=True, date_published__isnull=False)
    preprints_count = null_preprint_doi_created.count()
    current_preprint = 0
    logger.info('{} published preprints found with preprint_doi_created is null.'.format(preprints_count))
    ContentType = state.get_model('contenttypes', 'ContentType')
    Identifier = state.get_model('osf', 'identifier')

    with disable_auto_now_fields(models=[PreprintService]):
        for preprint in null_preprint_doi_created:
            current_preprint += 1
            content_type = ContentType.objects.get_for_model(preprint)
            if Identifier.objects.filter(object_id=preprint.id, category='doi', content_type=content_type).exists():
                preprint.preprint_doi_created = preprint.date_published
                preprint.save()
                logger.info('Preprint ID {}, {}/{} preprint_doi_created field populated.'.format(preprint.id, current_preprint, preprints_count))
            else:
                logger.info('Preprint ID {}, {}/{} skipped because a DOI has not been created.'.format(preprint.id, current_preprint, preprints_count))

def reverse_func(state, schema):
    """
    Reverses data migration. Sets preprint_doi_created field back to null.
    """
    PreprintService = state.get_model('osf', 'preprintservice')
    logger.info('Reversing preprint_doi_created migration.')
    PreprintService.objects.filter(preprint_doi_created__isnull=False).update(preprint_doi_created=None)

class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0068_preprintservice_preprint_doi_created'),
    ]

    operations = [
        migrations.RunPython(add_preprint_doi_created, reverse_func)
    ]
