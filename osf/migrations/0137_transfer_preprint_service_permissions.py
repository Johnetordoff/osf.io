# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-05-03 14:47
from __future__ import unicode_literals

from django.db import migrations
from django.core.management.sql import emit_post_migrate_signal


def unmigrate_preprint_service_permissions(state, schema):
    emit_post_migrate_signal(2, False, 'default')

    Permission = state.get_model('auth', 'permission')

    # New permission groups
    Permission.objects.filter(codename='add_preprint').update(
        codename='add_preprintservice', name='Can add preprint service'
    )
    Permission.objects.filter(codename='change_preprint').update(
        codename='change_preprintservice', name='Can change preprint service'
    )
    Permission.objects.filter(codename='delete_preprint').update(
        codename='delete_preprintservice', name='Can delete preprint service'
    )
    Permission.objects.filter(codename='view_preprint').update(
        codename='view_preprintservice',
        name='Can view preprint service details in the admin app.',
    )


def migrate_preprint_service_permissions(state, schema):
    """
    Django permissions on the preprint model have new names.
    """
    # this is to make sure that the permissions created earlier exist!
    emit_post_migrate_signal(2, False, 'default')

    Permission = state.get_model('auth', 'permission')

    Permission.objects.filter(codename='add_preprint').delete()
    Permission.objects.filter(codename='change_preprint').delete()
    Permission.objects.filter(codename='delete_preprint').delete()
    Permission.objects.filter(codename='view_preprint').delete()

    # Old permission groups
    Permission.objects.filter(codename='add_preprintservice').update(
        codename='add_preprint', name='Can add preprint'
    )
    Permission.objects.filter(codename='change_preprintservice').update(
        codename='change_preprint', name='Can change preprint'
    )
    Permission.objects.filter(codename='delete_preprintservice').update(
        codename='delete_preprint', name='Can delete preprint'
    )
    Permission.objects.filter(codename='view_preprintservice').update(
        codename='view_preprint', name='Can view preprint details in the admin app'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0136_preprint_node_divorce'),
    ]

    operations = [
        migrations.RunPython(
            migrate_preprint_service_permissions, unmigrate_preprint_service_permissions
        ),
    ]
