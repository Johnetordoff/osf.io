# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2017-04-06 21:14


from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0008_merge'),
    ]

    operations = [
        migrations.AlterField(
            model_name='noderelation',
            name='child',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='_parents', to='osf.AbstractNode'),
        ),
    ]
