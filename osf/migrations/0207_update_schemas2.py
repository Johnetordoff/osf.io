from __future__ import unicode_literals

from django.db import migrations
from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks, make_egap_active_but_invisible


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0207_ensure_schemas'),
    ]

    operations = [
        UpdateRegistrationSchemasAndSchemaBlocks(),
        migrations.RunPython(make_egap_active_but_invisible, migrations.RunPython.noop),
    ]
