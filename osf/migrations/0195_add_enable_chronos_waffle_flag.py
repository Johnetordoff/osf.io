# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-12-05 12:24
from __future__ import unicode_literals
from django.db import migrations

from osf import features
from osf.utils.migrations import AddWaffleFlags


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0194_merge_20191113_1611'),
    ]

    operations = [
        AddWaffleFlags([features.ENABLE_CHRONOS]),
    ]
