# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-05-18 14:33


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0030_preprint_provider_institution_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='preprintprovider',
            name='share_source',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
