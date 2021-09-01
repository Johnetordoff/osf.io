# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2021-09-01 12:47
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0235_auto_20210823_1310'),
    ]

    operations = [
        migrations.AlterField(
            model_name='schemaresponse',
            name='previous_response',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='updated_response', to='osf.SchemaResponse'),
        ),
        migrations.AlterField(
            model_name='schemaresponse',
            name='revision_justification',
            field=models.CharField(blank=True, max_length=2048, null=True),
        ),
        migrations.AlterField(
            model_name='schemaresponse',
            name='submitted_timestamp',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, null=True),
        ),
    ]
