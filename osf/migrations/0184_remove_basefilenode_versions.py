# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2019-04-08 00:51
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0183_populate_file_versions_through'),
    ]

    operations = [
        migrations.RemoveField(model_name='basefilenode', name='versions',),
    ]
