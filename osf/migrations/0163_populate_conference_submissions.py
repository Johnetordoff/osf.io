# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-06-08 15:12
from __future__ import unicode_literals
import logging
from django.db import migrations

logger = logging.getLogger(__file__)


def forward(state, *args, **kwargs):
    """
    For every conference, fetches all AbstractNodes with a case-insensitive matching Tag
    to the conference endpoint.  Adds these nodes to conference.submissions.
    """
    Conference = state.get_model('osf', 'Conference')
    AbstractNode = state.get_model('osf', 'AbstractNode')
    Tag = state.get_model('osf', 'Tag')

    # Small number of conferences
    for conference in Conference.objects.all():
        tags = Tag.objects.filter(
            system=False, name__iexact=conference.endpoint
        ).values_list('pk', flat=True)
        # Not restricting on public/deleted here, just adding all nodes with meeting tags
        # and then API will restrict to only public, non-deleted nodes
        for node in AbstractNode.objects.filter(tags__in=tags):
            conference.submissions.add(node)
    logger.info('Finished adding submissions to conferences.')


def backward(state, *args, **kwargs):
    Conference = state.get_model('osf', 'Conference')
    for conference in Conference.objects.all():
        for submission in conference.submissions.all():
            conference.submissions.remove(submission)
    logger.info('Finished clearing submissions from conferences.')


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0162_conference_submissions'),
    ]

    operations = [migrations.RunPython(forward, backward)]
