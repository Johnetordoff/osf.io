from __future__ import unicode_literals

from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks, make_egap_active_but_invisible

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0195_add_enable_chronos_waffle_flag'),
    ]

    operations = [
        UpdateRegistrationSchemasAndSchemaBlocks(),
        migrations.RunPython(make_egap_active_but_invisible, migrations.RunPython.noop),
    ]
