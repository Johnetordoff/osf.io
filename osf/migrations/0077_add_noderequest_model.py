# -*- coding: utf-8 -*-
# Generated by Django 1.11.7 on 2017-11-16 20:26
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import osf.models.base
import osf.utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0076_action_rename'),
    ]

    operations = [
        migrations.CreateModel(
            name='NodeRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('_id', models.CharField(db_index=True, default=osf.models.base.generate_object_id, max_length=24, unique=True)),
                ('machine_state', models.CharField(choices=[('accepted', 'Accepted'), ('initial', 'Initial'), ('pending', 'Pending'), ('rejected', 'Rejected')], db_index=True, default='initial', max_length=15)),
                ('date_last_transitioned', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('request_type', models.CharField(choices=[('access', 'Access')], max_length=31)),
                ('comment', models.TextField(blank=True, null=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submitted_requests', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='NodeRequestAction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('_id', models.CharField(db_index=True, default=osf.models.base.generate_object_id, max_length=24, unique=True)),
                ('trigger', models.CharField(choices=[('accept', 'Accept'), ('edit_comment', 'Edit_Comment'), ('reject', 'Reject'), ('submit', 'Submit')], max_length=31)),
                ('from_state', models.CharField(choices=[('accepted', 'Accepted'), ('initial', 'Initial'), ('pending', 'Pending'), ('rejected', 'Rejected')], max_length=31)),
                ('to_state', models.CharField(choices=[('accepted', 'Accepted'), ('initial', 'Initial'), ('pending', 'Pending'), ('rejected', 'Rejected')], max_length=31)),
                ('comment', models.TextField(blank=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('creator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('target', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='osf.NodeRequest')),
            ],
            options={
                'abstract': False,
            },
        ),
        # We add the access_requests_enabled field in two steps
        #    1. Add the field
        #    2. Adding a default value of True
        # This prevents an expensive table rewrite from locking the node table.
        migrations.AddField(
            model_name='abstractnode',
            name='access_requests_enabled',
            field=models.BooleanField(db_index=True, null=True),
        ),
        # Adding a default does not require a table rewrite
        migrations.RunSQL(
            [
                'ALTER TABLE "osf_abstractnode" ALTER COLUMN "access_requests_enabled" SET DEFAULT TRUE',
                'ALTER TABLE "osf_abstractnode" ALTER COLUMN "access_requests_enabled" DROP DEFAULT;',
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='abstractnode',
                    name='access_requests_enabled',
                    field=models.BooleanField(default=True, db_index=True, null=True),
                )
            ],
        ),
        migrations.AddField(
            model_name='noderequest',
            name='target',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requests', to='osf.AbstractNode'),
        ),
        migrations.AlterUniqueTogether(
            name='noderequest',
            unique_together=set([('target', 'creator')]),
        ),
    ]
