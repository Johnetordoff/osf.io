# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-09-26 20:08
from __future__ import unicode_literals

import logging
from django.db import migrations
from osf.utils.migrations import map_schemas_to_schemablocks, unmap_schemablocks
from osf.migrations.utils.utils import remove_version_1_schemas, update_schemaless_registrations, update_schema_configs, unset_schema_configs

logger = logging.getLogger(__file__)


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0190_add_schema_block_models')
    ]

    operations = [
        migrations.RunPython(remove_version_1_schemas, migrations.RunPython.noop),
        migrations.RunPython(update_schemaless_registrations, migrations.RunPython.noop),
        migrations.RunPython(update_schema_configs, unset_schema_configs),
        migrations.RunPython(map_schemas_to_schemablocks, unmap_schemablocks)
    ]
