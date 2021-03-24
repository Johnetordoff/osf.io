import logging

import json
from math import ceil

logger = logging.getLogger(__file__)
from osf.models import RegistrationSchema
from osf.utils.migrations import ensure_schemas
from website.project.metadata.schemas import ensure_schema_structure, from_json
from osf.utils.migrations import UpdateRegistrationSchemasAndSchemaBlocks
from osf.management.commands.migrate_pagecounter_data import FORWARD_SQL, REVERSE_SQL

from django.db import migrations, connection

logger = logging.getLogger(__name__)
from website import settings

increment = 500000

def populate_blacklisted_domains(state, *args, **kwargs):
    BlacklistedEmailDomain = state.get_model('osf', 'BlacklistedEmailDomain')
    BlacklistedEmailDomain.objects.bulk_create([
        BlacklistedEmailDomain(domain=domain)
        for domain in settings.BLACKLISTED_DOMAINS
    ])

def remove_blacklisted_domains(state, *args, **kwargs):
    BlacklistedEmailDomain = state.get_model('osf', 'BlacklistedEmailDomain')
    BlacklistedEmailDomain.objects.all().delete()



def add_schema(apps, schema_editor):
    schema = ensure_schema_structure(from_json('secondary-data.json'))

    RegistrationSchema.objects.filter(name=schema['name']).update(visible=False, active=True)

def add_datacite_schema(state, schema):
    FileMetadataSchema = state.get_model('osf', 'filemetadataschema')
    with open('osf/metadata/schemas/datacite.json') as f:
        jsonschema = json.load(f)
    _, created = FileMetadataSchema.objects.get_or_create(
        _id='datacite',
        schema_version=1,
        defaults={
            'name': 'datacite',
            'schema': jsonschema
        }

    )
    if created:
        logger.info('Added datacite schema to the database')


def remove_datacite_schema(state, schema):
    FileMetadataSchema = state.get_model('osf', 'filemetadataschema')
    FileMetadataSchema.objects.get(_id='datacite').delete()
    logger.info('Removed datacite schema from the database')


def add_records_to_files_sql(state, schema):
    FileMetadataSchema = state.get_model('osf', 'filemetadataschema')
    datacite_schema_id = FileMetadataSchema.objects.filter(_id='datacite').values_list('id', flat=True)[0]
    OsfStorageFile = state.get_model('osf', 'osfstoragefile')
    max_fid = getattr(OsfStorageFile.objects.last(), 'id', 0)

    sql = """
        INSERT INTO osf_filemetadatarecord (created, modified, _id, metadata, file_id, schema_id)
        SELECT NOW(), NOW(), generate_object_id(), '{{}}', OSF_FILE.id, %d
            FROM osf_basefilenode OSF_FILE
                WHERE (OSF_FILE.type = 'osf.osfstoragefile'
                       AND OSF_FILE.provider = 'osfstorage'
                       AND OSF_FILE.id > {}
                       AND OSF_FILE.id <= {}
                );
    """ % (datacite_schema_id)

    total_pages = int(ceil(max_fid / float(increment)))
    page_start = 0
    page_end = 0
    page = 0
    while page_end <= (max_fid):
        page += 1
        page_end += increment
        if page <= total_pages:
            logger.info('Updating page {} / {}'.format(page_end / increment, total_pages))
        with connection.cursor() as cursor:
            cursor.execute(sql.format(
                page_start,
                page_end
            ))
        page_start = page_end


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0002_adminlogentry'),
    ]

    operations = [
        UpdateRegistrationSchemasAndSchemaBlocks(),
        migrations.RunPython(add_schema, ensure_schemas),
        migrations.RunSQL([
            'CREATE INDEX nodelog__node_id_date_desc on osf_nodelog (node_id, date DESC);',
            # 'VACUUM ANALYZE osf_nodelog;'  # Run this manually, requires ~3 min downtime
        ], [
            'DROP INDEX IF EXISTS nodelog__node_id_date_desc RESTRICT;',
        ]),
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
        migrations.RunSQL(
            """
            SELECT setval(pg_get_serial_sequence('"osf_abstractprovider_licenses_acceptable"','id'),
                        coalesce(max("id"), 1), max("id") IS NOT null)
            FROM "osf_abstractprovider_licenses_acceptable";
            SELECT setval(pg_get_serial_sequence('"osf_abstractprovider"','id'),
                        coalesce(max("id"), 1), max("id") IS NOT null)
            FROM "osf_abstractprovider";
            """,
            """
            SELECT setval(pg_get_serial_sequence('"osf_abstractprovider_licenses_acceptable"','id'), 1, max("id") IS NOT null)
            FROM "osf_abstractprovider_licenses_acceptable";
            SELECT setval(pg_get_serial_sequence('"osf_abstractprovider"','id'), 1, max("id") IS NOT null)
            FROM "osf_abstractprovider_licenses_acceptable";
            """
        ),
        migrations.RunSQL(
            [
                """
                CREATE INDEX osf_abstractnode_registered_date_index ON public.osf_abstractnode (registered_date DESC);
                CREATE INDEX osf_abstractnode_registration_pub_del_type_index ON public.osf_abstractnode (is_public, is_deleted, type) WHERE is_public=TRUE and is_deleted=FALSE and type = 'osf.registration';
                CREATE INDEX osf_abstractnode_node_pub_del_type_index ON public.osf_abstractnode (is_public, is_deleted, type) WHERE is_public=TRUE and is_deleted=FALSE and type = 'osf.node';
                CREATE INDEX osf_abstractnode_collection_pub_del_type_index ON public.osf_abstractnode (is_public, is_deleted, type) WHERE is_public=TRUE and is_deleted=FALSE and type = 'osf.collection';
                """
            ],
            [
                """
                DROP INDEX public.osf_abstractnode_registered_date_index RESTRICT;
                DROP INDEX public.osf_abstractnode_registration_pub_del_type_index RESTRICT;
                DROP INDEX public.osf_abstractnode_node_pub_del_type_index RESTRICT;
                DROP INDEX public.osf_abstractnode_collection_pub_del_type_index RESTRICT;
                """
            ]
        ),
        migrations.RunSQL(
            [
                """
                CREATE UNIQUE INDEX osf_basefilenode_non_trashed_unique_index
                ON public.osf_basefilenode
                (target_object_id, name, parent_id, type, _path)
                WHERE type NOT IN ('osf.trashedfilenode', 'osf.trashedfile', 'osf.trashedfolder');
                """,
            ],
            [
                """
                DROP INDEX public.osf_basefilenode_non_trashed_unique_index RESTRICT;
                """
            ]
        ),
        migrations.RunPython(add_datacite_schema, migrations.RunPython.noop),
        migrations.RunSQL("""
                -- Borrowed from https://gist.github.com/jamarparris/6100413
                CREATE OR REPLACE FUNCTION generate_object_id() RETURNS varchar AS $$
                DECLARE
                    time_component bigint;
                    machine_id bigint := FLOOR(random() * 16777215);
                    process_id bigint;
                    seq_id bigint := FLOOR(random() * 16777215);
                    result varchar:= '';
                BEGIN
                    SELECT FLOOR(EXTRACT(EPOCH FROM clock_timestamp())) INTO time_component;
                    SELECT pg_backend_pid() INTO process_id;
                    result := result || lpad(to_hex(time_component), 8, '0');
                    result := result || lpad(to_hex(machine_id), 6, '0');
                    result := result || lpad(to_hex(process_id), 4, '0');
                    result := result || lpad(to_hex(seq_id), 6, '0');
                    RETURN result;
                END;
                $$ LANGUAGE PLPGSQL;
                """,
                          migrations.RunPython.noop),
        migrations.RunPython(add_records_to_files_sql, migrations.RunPython.noop),
        migrations.RunPython(populate_blacklisted_domains, remove_blacklisted_domains),
    ]
