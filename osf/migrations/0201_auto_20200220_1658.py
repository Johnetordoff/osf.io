# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2020-02-20 16:58
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0200_auto_20200214_1518'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='institution',
            options={'permissions': (('view_institution', 'Can view institution details'), ('view_institutional_metrics', 'Can access metrics endpoints for their Institution'))},
        ),
    ]
