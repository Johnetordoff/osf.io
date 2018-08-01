# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-13 16:25

import pytz

import datetime
from django.db import migrations
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('addons_twofactor', '0002_usersettings_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, default=datetime.datetime(1970, 1, 1, 0, 0, tzinfo=pytz.utc), verbose_name='created'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='usersettings',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified'),
        ),
    ]
