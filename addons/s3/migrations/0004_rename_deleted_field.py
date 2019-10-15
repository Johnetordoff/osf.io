# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-06-27 20:29
from __future__ import unicode_literals

from django.db import migrations
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('addons_s3', '0003_auto_20170713_1125'),
    ]

    operations = [
        migrations.RenameField(
            model_name='nodesettings',
            new_name='is_deleted',
            old_name='deleted',
        ),
        migrations.RenameField(
            model_name='usersettings',
            new_name='is_deleted',
            old_name='deleted',
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='deleted',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usersettings',
            name='deleted',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, null=True),
        ),
    ]
