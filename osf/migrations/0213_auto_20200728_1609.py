# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-07-28 16:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0212_registrationschema_providers'),
    ]

    operations = [
        migrations.AlterField(
            model_name='draftregistration',
            name='provider',
            field=models.ForeignKey(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='draft_registrations',
                to='osf.RegistrationProvider'
            ),
        ),
    ]
