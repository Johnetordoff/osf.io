# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-12-13 16:02
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
import osf.utils.fields
from website import settings


def populate_blacklisted_domains(state, *args, **kwargs):
    BlacklistedEmailDomain = state.get_model('osf', 'BlacklistedEmailDomain')
    blacklisted_domains = getattr(settings, 'BLACKLISTED_DOMAINS')
    BlacklistedEmailDomain.objects.bulk_create(
        [BlacklistedEmailDomain(domain=domain) for domain in blacklisted_domains]
    )


def remove_blacklisted_domains(state, *args, **kwargs):
    BlacklistedEmailDomain = state.get_model('osf', 'BlacklistedEmailDomain')
    BlacklistedEmailDomain.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0146_update_registration_schemas'),
    ]

    operations = [
        migrations.CreateModel(
            name='BlacklistedEmailDomain',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'created',
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name='created'
                    ),
                ),
                (
                    'modified',
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name='modified'
                    ),
                ),
                (
                    'domain',
                    osf.utils.fields.LowercaseCharField(
                        db_index=True, max_length=255, unique=True
                    ),
                ),
            ],
            options={'abstract': False,},
        ),
        migrations.RunPython(populate_blacklisted_domains, remove_blacklisted_domains),
    ]
