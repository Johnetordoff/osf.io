# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-06-02 14:23


from django.db import migrations

def add_slash_to_implict_folders(apps, schema_editor):
    NodeLog = apps.get_model('osf', 'NodeLog')
    logs = NodeLog.objects.raw('''select * from osf_nodelog where osf_nodelog.action = 'owncloud_file_removed';''')
    for log in logs:
        if not ('.' in log.params['path'] and len(log.params['path'].split('.')[-1]) <= 5):  # if it has ext we assume its a file.
            log.params['path'] += '/'
            log.save()


def remove_slash_to_implict_folders(apps, schema_editor):
    NodeLog = apps.get_model('osf', 'NodeLog')
    logs = NodeLog.objects.raw('''select * from osf_nodelog where osf_nodelog.action = 'owncloud_file_removed';''')
    for log in logs:
        if '.' in log.params['path'] and len(log.params['path'].split('.')[-1]) <= 5:  # if it has ext we assume its a file.
            log.params['path'] = log.params['path'].strip('/')
            log.save()


class Migration(migrations.Migration):

    dependencies = [
        ('addons_owncloud', '0002_auto_20170323_1534'),
    ]

    operations = [
        migrations.RunPython(add_slash_to_implict_folders, remove_slash_to_implict_folders)
    ]
