# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-10-12 17:36
from __future__ import unicode_literals

import logging
from django.db import migrations, models
import django.db.models.deletion

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('osf', '0082_merge_20180213_1502'),
    ]

    operations = [
        migrations.AddField(
            model_name='basefilenode',
            name='target_content_type',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='basefilenode_target',
                to='contenttypes.ContentType',
            ),
        ),
        migrations.AddField(
            model_name='basefilenode',
            name='target_object_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='basefilenode', name='is_root', field=models.NullBooleanField(),
        ),
    ]
