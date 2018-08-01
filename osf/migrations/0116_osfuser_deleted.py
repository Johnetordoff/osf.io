# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-07-10 16:05


from django.db import migrations
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0115_auto_20180628_1253'),
    ]

    operations = [
        migrations.AddField(
            model_name='osfuser',
            name='deleted',
            field=osf.utils.fields.NonNaiveDateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
