# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2020-03-23 18:50
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0204_ensure_schemas'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='institution',
            options={'permissions': (('view_institutional_metrics', 'Can access metrics endpoints for their Institution'),)},
        ),
        migrations.AddField(
            model_name='osfuser',
            name='department',
            field=models.TextField(blank=True, null=True),
        ),
    ]
