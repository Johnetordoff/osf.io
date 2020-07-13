# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-07-13 15:25
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0067_auto_20171121_1050'),
    ]

    operations = [
        migrations.AlterField(
            model_name='abstractnode',
            name='creator',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='nodes_created',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RenameField(
            model_name='comment', old_name='modified', new_name='edited'
        ),
    ]
