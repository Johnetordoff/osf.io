# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-09-01 23:15
from __future__ import unicode_literals

from django.db import migrations, models
import osf.utils.datetime_aware_jsonfield


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0191_migrate_schemas_to_schemablocks'),
    ]

    operations = [
        migrations.AddField(
            model_name='abstractnode',
            name='registration_responses',
            field=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(
                blank=True,
                default=dict,
                encoder=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONEncoder,
            ),
        ),
        migrations.AddField(
            model_name='abstractnode',
            name='registration_responses_migrated',
            field=models.NullBooleanField(db_index=True),
        ),
        migrations.AddField(
            model_name='draftregistration',
            name='registration_responses',
            field=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONField(
                blank=True,
                default=dict,
                encoder=osf.utils.datetime_aware_jsonfield.DateTimeAwareJSONEncoder,
            ),
        ),
        migrations.AddField(
            model_name='draftregistration',
            name='registration_responses_migrated',
            field=models.NullBooleanField(db_index=True),
        ),
        migrations.AlterField(
            model_name='abstractnode',
            name='registration_responses_migrated',
            field=models.NullBooleanField(db_index=True, default=True),
        ),
        migrations.AlterField(
            model_name='draftregistration',
            name='registration_responses_migrated',
            field=models.NullBooleanField(db_index=True, default=True),
        ),
    ]
