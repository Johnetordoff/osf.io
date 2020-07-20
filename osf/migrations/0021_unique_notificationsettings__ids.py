# -*- coding: utf-8 -*-
# This is an auto-migration and not a management command because:
#   1. The next script would fail if duplicate records existed
#   2. This should only need to be run once
from __future__ import unicode_literals
import logging

from django.db import migrations

logger = logging.getLogger(__file__)


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0021_retraction_date_retracted'),
    ]

    operations = [
        migrations.RunPython(
            migrations.RunPython.noop, migrations.RunPython.noop
        ),
    ]
