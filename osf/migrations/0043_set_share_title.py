# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-08-03 15:07
"""Sets the share_title field on production PreprintProviders. Makes no
updates if the listed providers don't exist in the current envirionment.
"""
from __future__ import unicode_literals

from django.db import migrations

# _id => share_title
SHARE_TITLES = {
    'osf': 'OSF',
    'lawarxiv': 'LawArXiv',
    'mindrxiv': 'MindRxiv',
    'bitss': 'BITSS',
    'agrixiv': 'AgriXiv',
    'engrxiv': 'engrXiv',
    'lissa': 'LIS Scholarship Archive',
    'psyarxiv': 'PsyArXiv',
    'socarxiv': 'SocArXiv',
}


def set_share_titles(state, *args, **kwargs):
    PreprintProvider = state.get_model('osf', 'preprintprovider')
    for provider in PreprintProvider.objects.filter(_id__in=list(SHARE_TITLES.keys())):
        provider.share_title = SHARE_TITLES[provider._id]
        provider.save()


def unset_share_titles(state, *args, **kwargs):
    PreprintProvider = state.get_model('osf', 'preprintprovider')
    PreprintProvider.objects.filter(_id__in=list(SHARE_TITLES.keys())).update(
        share_title=''
    )


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0042_preprintprovider_share_title'),
    ]

    operations = [
        migrations.RunPython(set_share_titles, unset_share_titles),
    ]
