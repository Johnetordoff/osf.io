# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-09-07 14:32
from __future__ import unicode_literals

from django.db import migrations, models
import osf.models.notable_domain


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0250_auto_20220907_1429'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notabledomain',
            name='domain',
            field=models.URLField(db_index=True, max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='notabledomain',
            name='note',
            field=models.IntegerField(choices=[(0, 'SPAM'), (1, 'HAM'), (2, 'UNKNOWN')], default=osf.models.notable_domain.Note(0)),
        ),
    ]
