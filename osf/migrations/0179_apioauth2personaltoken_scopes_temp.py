# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-10-17 23:30
from __future__ import unicode_literals

from django.db import migrations, models

"""
2-part migration to make scopes an m2m field instead of a charfield on tokens

This migration:
1. Makes scopes field nullable
2. Adds a scopes_temp field
3. Copies scopes information from scopes field to scopes temp (char -> m2m)

0171_finalize_token_scopes_mig:
1. Removes old scopes field (charfield)
2. Renames scopes_temp -> scopes

"""
"""
Some tokens have the following scopes on staging, existing prior to
https://github.com/CenterForOpenScience/osf.io/pull/5959.
Also, some staging scopes aren't public scopes, and would have to be loaded
in with public=False.
"""
old_scope_mapping = {
    'osf.users.all_read': 'osf.users.profile_read',
    'osf.users.all_write': 'osf.users.profile_write',
    'osf.nodes.all_read': 'osf.nodes.full_read',
    'osf.nodes.all_write': 'osf.nodes.full_write',
}


def remove_m2m_scopes(state, schema):
    ApiOAuth2PersonalToken = state.get_model('osf', 'apioauth2personaltoken')
    tokens = ApiOAuth2PersonalToken.objects.all()
    for token in tokens:
        token.scopes = ' '.join([scope.name for scope in token.scopes_temp.all()])
        token.scopes_temp.clear()
        token.save()


def migrate_scopes_from_char_to_m2m(state, schema):
    ApiOAuth2PersonalToken = state.get_model('osf', 'apioauth2personaltoken')
    ApiOAuth2Scope = state.get_model('osf', 'apioauth2scope')

    tokens = ApiOAuth2PersonalToken.objects.all()
    for token in tokens:
        string_scopes = token.scopes.split(' ')
        for scope in string_scopes:
            loaded_scope = ApiOAuth2Scope.objects.get(
                name=old_scope_mapping.get(scope, scope)
            )
            token.scopes_temp.add(loaded_scope)
            token.save()


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0178_apioauth2scope_is_public'),
    ]

    # AlterField migration added to set null=True because when reverting 0171_finalize_token_scopes_mig,
    # scopes will be renamed to scopes_temp, and a scopes field will be restored.  That scopes
    # field would be empty until this migration was run, but null needs to be True to all this.
    operations = [
        migrations.AlterField(
            model_name='apioauth2personaltoken',
            name='scopes',
            field=models.CharField(blank=False, null=True, max_length=300),
        ),
        migrations.AddField(
            model_name='apioauth2personaltoken',
            name='scopes_temp',
            field=models.ManyToManyField(
                related_name='tokens', to='osf.ApiOAuth2Scope'
            ),
        ),
        migrations.RunPython(migrate_scopes_from_char_to_m2m, remove_m2m_scopes),
    ]
