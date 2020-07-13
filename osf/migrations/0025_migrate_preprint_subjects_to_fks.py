# -*- coding: utf-8 -*-
# Generated by Django 1.9 on 2017-04-17 19:58
from __future__ import unicode_literals

from django.db import migrations, models


def migrate_data(state, schema):
    Preprint = state.get_model('osf', 'preprintservice')
    Subject = state.get_model('osf', 'subject')
    # Avoid updating date_modified for migration
    field = Preprint._meta.get_field('date_modified')
    field.auto_now = False
    for pp in Preprint.objects.all():
        for s_id in list(set(sum(pp.subjects, []))):
            s = Subject.objects.get(_id=s_id)
            pp._subjects.add(s)
        pp.save()
    field.auto_now = True


def unmigrate_data(state, scheme):
    Preprint = state.get_model('osf', 'preprintservice')
    # Avoid updating date_modified for migration
    field = Preprint._meta.get_field('date_modified')
    field.auto_now = False
    for pp in Preprint.objects.all():
        pp.subjects = [[s._id for s in hier] for hier in pp.subject_hierarchy]
        pp.save()
    field.auto_now = True


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0024_migrate_subject_parents_to_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='preprintservice',
            name='_subjects',
            field=models.ManyToManyField(
                blank=True, related_name='preprint_services', to='osf.Subject'
            ),
        ),
        migrations.RunPython(migrate_data, unmigrate_data),
    ]
