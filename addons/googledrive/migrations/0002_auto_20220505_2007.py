# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-05-05 20:07
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('addons_googledrive', '0001_initial'),
        ('osf', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='owner',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addons_googledrive_user_settings', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='external_account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addons_googledrive_node_settings', to='osf.ExternalAccount'),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='owner',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addons_googledrive_node_settings', to='osf.AbstractNode'),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='user_settings',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='addons_googledrive.UserSettings'),
        ),
    ]
