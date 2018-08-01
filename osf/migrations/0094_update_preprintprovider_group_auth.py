# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-03-28 03:41


from django.core.management.sql import emit_post_migrate_signal
from django.db import migrations

from api.providers.permissions import GroupHelper

def update_group_auth(apps, schema):
    emit_post_migrate_signal(2, False, 'default')
    PreprintProvider = apps.get_model('osf', 'preprintprovider')
    [GroupHelper(each).update_provider_auth_groups() for each in PreprintProvider.objects.all()]

def noop(*args, **kwargs):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0093_node_subjects'),
    ]

    operations = [
        migrations.RunPython(update_group_auth, noop)
    ]
