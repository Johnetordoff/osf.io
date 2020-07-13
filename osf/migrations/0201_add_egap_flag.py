# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2019-07-23 14:26
from __future__ import unicode_literals
from django.db import migrations

from osf import features
from osf.utils.migrations import AddWaffleFlags


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0200_auto_20200214_1518'),
    ]

    operations = [
        AddWaffleFlags([features.EGAP_ADMINS], on_for_everyone=None),
    ]
