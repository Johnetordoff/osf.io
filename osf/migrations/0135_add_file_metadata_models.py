# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-07-27 14:42
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
import osf.models.base
import osf.utils.datetime_aware_jsonfield


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0134_abstractnode_custom_citation'),
    ]

    operations = [
        migrations.CreateModel(
            name='FileMetadataSchema',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'created',
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name='created'
                    ),
                ),
                (
                    'modified',
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name='modified'
                    ),
                ),
                (
                    '_id',
                    models.CharField(
                        db_index=True,
                        default=osf.models.base.generate_object_id,
                        max_length=24,
                        unique=True,
                    ),
                ),
                ('name', models.CharField(max_length=255)),
                (
                    'schema',
                    osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(
                        default=dict,
                        encoder=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONEncoder,
                    ),
                ),
                ('category', models.CharField(blank=True, max_length=255, null=True)),
                ('active', models.BooleanField(default=True)),
                ('schema_version', models.IntegerField()),
                ('visible', models.BooleanField(default=True)),
            ],
            options={'abstract': False,},
        ),
        migrations.AlterUniqueTogether(
            name='filemetadataschema',
            unique_together=set([('name', 'schema_version')]),
        ),
        migrations.CreateModel(
            name='FileMetadataRecord',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'created',
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name='created'
                    ),
                ),
                (
                    'modified',
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name='modified'
                    ),
                ),
                (
                    '_id',
                    models.CharField(
                        db_index=True,
                        default=osf.models.base.generate_object_id,
                        max_length=24,
                        unique=True,
                    ),
                ),
                (
                    'metadata',
                    osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(
                        blank=True,
                        default=dict,
                        encoder=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONEncoder,
                    ),
                ),
                (
                    'file',
                    models.ForeignKey(
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='records',
                        to='osf.OsfStorageFile',
                    ),
                ),
                (
                    'schema',
                    models.ForeignKey(
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='records',
                        to='osf.FileMetadataSchema',
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='filemetadatarecord', unique_together=set([('file', 'schema')]),
        ),
    ]
