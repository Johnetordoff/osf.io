# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-12-12 18:52
from __future__ import unicode_literals

from django.db import migrations
from scripts.divorce_quickfiles import divorce_quickfiles, reverse_divorce_quickfiles

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0162_auto_20190614_1429')
    ]

    operations = [
        migrations.RunPython(divorce_quickfiles, reverse_divorce_quickfiles)
    ]
