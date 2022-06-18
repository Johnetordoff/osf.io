# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-07-19 16:51
from __future__ import unicode_literals
from waffle.models import Flag
from django.db import migrations


def reverse_func(state, schema):
    flag = Flag(name='ember_support_page', everyone=False)
    flag.save()


def remove_support_page_waffle_flags(state, schema):
    Flag.objects.get(name='ember_support_page').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0120_merge_20180716_1457'),
    ]

    operations = [
    ]
