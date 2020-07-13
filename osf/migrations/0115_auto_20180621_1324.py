# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-06-21 18:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0114_merge_20180621_1322'),
    ]

    operations = [
        migrations.AlterField(
            model_name='providerassetfile',
            name='name',
            field=models.CharField(
                choices=[
                    ('favicon', 'favicon'),
                    ('powered_by_share', 'powered_by_share'),
                    ('sharing', 'sharing'),
                    ('square_color_no_transparent', 'square_color_no_transparent'),
                    ('square_color_transparent', 'square_color_transparent'),
                    ('style', 'style'),
                    ('wide_black', 'wide_black'),
                    ('wide_color', 'wide_color'),
                    ('wide_white', 'wide_white'),
                ],
                max_length=63,
            ),
        ),
    ]
