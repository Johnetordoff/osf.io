# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-04-06 16:52


import logging

from django.db import migrations
from osf.utils.migrations import ensure_licenses, remove_licenses


logger = logging.getLogger(__file__)


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0094_update_preprintprovider_group_auth'),
    ]

    operations = [
        migrations.RunPython(ensure_licenses, remove_licenses),
    ]
