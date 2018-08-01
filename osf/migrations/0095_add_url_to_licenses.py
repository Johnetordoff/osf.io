# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-04-17 20:57


from django.db import migrations, models
from osf.utils.migrations import ensure_licenses, remove_licenses


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0094_update_preprintprovider_group_auth'),
    ]

    operations = [
        migrations.AddField(
            model_name='nodelicense',
            name='url',
            field=models.URLField(blank=True),
        ),
        migrations.RunPython(ensure_licenses, remove_licenses),
    ]
