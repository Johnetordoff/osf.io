# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2017-04-17 19:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0012_auto_20170411_1548'),
    ]

    operations = [
        migrations.AddField(
            model_name='institution',
            name='delegation_protocol',
            field=models.CharField(
                blank=True,
                choices=[
                    ('cas-pac4j', 'CAS by pac4j'),
                    ('oauth-pac4j', 'OAuth by pac4j'),
                    ('saml-shib', 'SAML by Shibboleth'),
                    ('', 'No Delegation Protocol'),
                ],
                default='',
                max_length=15,
            ),
        ),
        migrations.AlterField(
            model_name='institution',
            name='logo_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
