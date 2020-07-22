import os
import logging
from django.db import connection

from urllib.parse import quote, unquote
from django.db.models import F

from osf.utils.workflows import DefaultStates
from math import ceil

from django_bulk_update.helper import bulk_update
from osf.utils.migrations import disable_auto_now_fields
from osf.management.commands.add_notification_subscription import add_reviews_notification_setting

from addons.osfstorage.models import NodeSettings as OSFSNodeSettings, OsfStorageFolder
from osf.models import OSFUser, QuickFilesNode, Contributor, SpamStatus
from osf.models.base import ensure_guid
from osf.models.quickfiles import get_quickfiles_project_title
from lxml import etree
from django.db import models

from django.contrib.auth.models import Group
from guardian.shortcuts import assign_perm, get_perms, remove_perm
from osf.models import PreprintProvider
from django.apps import apps
from django.core.paginator import Paginator
from django.core.management.sql import emit_post_migrate_signal

from addons.osfstorage.settings import DEFAULT_REGION_NAME, DEFAULT_REGION_ID
from website.settings import WATERBUTLER_URL

from osf.management.commands.migrate_registration_responses import (
    migrate_draft_registrations,
    migrate_registrations
)

from website import settings

logger = logging.getLogger(__file__)
from waffle.models import Flag


def remove_duplicate_notificationsubscriptions(state, schema):
    NotificationSubscription = state.get_model('osf', 'notificationsubscription')
    # Deletes the newest from each set of duplicates
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT MAX(id)
            FROM osf_notificationsubscription
            GROUP BY _id HAVING COUNT(*) > 1;
        """)
        ids = list(sum(cursor.fetchall(), ()))
        logger.info('Deleting duplicate NotificationSubscriptions with `id`s {}'.format(ids))
        # Use Django to cascade delete through tables
        NotificationSubscription.objects.filter(id__in=ids).delete()
    NotificationSubscription.objects.all().delete()

def add_custom_mapping_constraint(state, schema):
    osf_id, created = state.get_model('osf', 'preprintprovider').objects.get_or_create(_id='osf')

    if created:
        osf_id.save()

    with connection.cursor() as cursor:
        cursor.execute(
            """ALTER TABLE osf_subject
            ADD CONSTRAINT customs_must_be_mapped
            CHECK (bepress_subject_id IS NOT NULL OR provider_id = %s);
            """,
            [osf_id.id]
        )


def remove_custom_mapping_constraint(*args):
    with connection.cursor() as cursor:
        cursor.execute("""
            ALTER TABLE osf_subject
            DROP CONSTRAINT IF EXISTS customs_must_be_mapped RESTRICT;
        """)


def unquote_folder_paths(state, schema):
    try:
        NodeSettings = state.get_model('addons_googledrive', 'nodesettings')
        targets = NodeSettings.objects.filter(folder_path__isnull=False)
    except LookupError:
        return
    for obj in targets:
        try:
            obj.folder_path = unquote(obj.folder_path).decode('utf-8')
        except UnicodeEncodeError:
            obj.folder_path = unquote(obj.folder_path)
    bulk_update(targets, update_fields=['folder_path'])


def quote_folder_paths(state, schema):
    try:
        NodeSettings = state.get_model('addons_googledrive', 'nodesettings')
        targets = NodeSettings.objects.filter(folder_path__isnull=False)
    except LookupError:
        return
    for obj in targets:
        obj.folder_path = quote(obj.folder_path.encode('utf-8'))
    bulk_update(targets, update_fields=['folder_path'])


def create_emails(user, Email):
    uid = user['id']
    primary_email = user['username'].lower().strip()
    emails = set([e.lower().strip() for e in user['emails']])
    active = user['is_active']
    if active or not Email.objects.filter(address=primary_email).exists():
        _, created = Email.objects.get_or_create(address=primary_email, user_id=uid)
        assert created, 'Email object for username {} already exists'.format(primary_email)
    for email in emails:
        if email == primary_email:
            # Already created above
            continue
        if active or not Email.objects.filter(address=email).exists():
            _, created = Email.objects.get_or_create(address=email, user_id=uid)
            assert created, 'Email object for email {} on user {} already exists'.format(email, uid)


def populate_email_model(state, schema):
    # Note: it is expected that any duplicates have been merged before this is ran.
    # If not, this will error
    OSFUser = state.get_model('osf', 'osfuser')
    Email = state.get_model('osf', 'email')
    for user in OSFUser.objects.filter(is_active=True).values('id', 'username', 'emails', 'is_active'):
        # Give priority to active users
        create_emails(user, Email)
    for user in OSFUser.objects.filter(is_active=False, merged_by__isnull=True).values('id', 'username', 'emails', 'is_active'):
        create_emails(user, Email)


def restore_old_emails(state, schema):
    # Not possible with complete accuracy -- some disabled users may have lost info
    Email = state.get_model('osf', 'email')
    for email in Email.objects.all():
        if email.address not in email.user.emails:
            email.user.emails.append(email.address)
            email.user.save()


def remove_emails(state, *args, **kwargs):
    Email = state.get_model('osf', 'email')
    Email.objects.filter(user__date_confirmed__isnull=True).delete()


# copied from 0033_user_emails_to_fk
def restore_emails(state, *args, **kwargs):
    Email = state.get_model('osf', 'email')
    OSFUser = state.get_model('osf', 'osfuser')
    for user in OSFUser.objects.filter(date_confirmed__isnull=True).values('id', 'username', 'is_active'):
        uid = user['id']
        primary_email = user['username'].lower().strip()
        active = user['is_active']
        if active or not Email.objects.filter(address=primary_email).exists():
            _, created = Email.objects.get_or_create(address=primary_email, user_id=uid)
            assert created, 'Email object for username {} already exists'.format(primary_email)


SHARE_TITLES = {
    'osf': 'OSF',
    'lawarxiv': 'LawArXiv',
    'mindrxiv': 'MindRxiv',
    'bitss': 'BITSS',
    'agrixiv': 'AgriXiv',
    'engrxiv': 'engrXiv',
    'lissa': 'LIS Scholarship Archive',
    'psyarxiv': 'PsyArXiv',
    'socarxiv': 'SocArXiv',
}


def set_share_titles(state, *args, **kwargs):
    PreprintProvider = state.get_model('osf', 'preprintprovider')
    for provider in PreprintProvider.objects.filter(_id__in=list(SHARE_TITLES.keys())):
        provider.share_title = SHARE_TITLES[provider._id]
        provider.save()


def unset_share_titles(state, *args, **kwargs):
    PreprintProvider = state.get_model('osf', 'preprintprovider')
    PreprintProvider.objects.filter(_id__in=list(SHARE_TITLES.keys())).update(share_title='')


def remove_duplicate_filenodes(*args):
    from osf.models.files import BaseFileNode
    sql = """
        SELECT id
        FROM (SELECT
                *,
                LEAD(row, 1)
                OVER () AS nextrow
              FROM (SELECT
                      *,
                      ROW_NUMBER()
                      OVER (w) AS row
                    FROM (SELECT *
                          FROM osf_basefilenode
                          WHERE (node_id IS NULL OR name IS NULL OR parent_id IS NULL OR type IS NULL OR _path IS NULL) AND
                                type NOT IN ('osf.trashedfilenode', 'osf.trashedfile', 'osf.trashedfolder')) AS null_files
                    WINDOW w AS (
                      PARTITION BY node_id, name, parent_id, type, _path
                      ORDER BY id )) AS x) AS y
        WHERE row > 1 OR nextrow > 1;
    """
    visited = []
    with connection.cursor() as cursor:
        cursor.execute(sql)
        dupes = BaseFileNode.objects.filter(id__in=[t[0] for t in cursor.fetchall()])
        logger.info('\nFound {} dupes, merging and removing'.format(dupes.count()))
        for dupe in dupes:
            visited.append(dupe.id)
            force = False
            next_dupe = dupes.exclude(id__in=visited).filter(node_id=dupe.node_id, name=dupe.name, parent_id=dupe.parent_id, type=dupe.type, _path=dupe._path).first()
            if dupe.node_id is None:
                # Bad data, force-delete
                force = True
            if not next_dupe:
                # Last one, don't delete
                continue
            if dupe.versions.count() > 1:
                logger.warn('{} Expected 0 or 1 versions, got {}'.format(dupe.id, dupe.versions.count()))
                # Don't modify versioned files
                continue
            for guid in list(dupe.guids.all()):
                guid.referent = next_dupe
                guid.save()
            if force:
                BaseFileNode.objects.filter(id=dupe.id).delete()
            else:
                dupe.delete()
    with connection.cursor() as cursor:
        logger.info('Validating clean-up success...')
        cursor.execute(sql)
        dupes = BaseFileNode.objects.filter(id__in=cursor.fetchall())
        if dupes.exists():
            logger.error('Dupes exist after migration, failing\n{}'.format(dupes.values_list('id', flat=True)))
    logger.info('Indexing...')


def migrate_user_guid_array_to_m2m(state, schema):
    from osf.models import OSFUser as FindableOSFUser
    AddableOSFUser = state.get_model('osf', 'osfuser')
    Comment = state.get_model('osf', 'comment')
    for comment in Comment.objects.exclude(_ever_mentioned=[]).all():
        for user in AddableOSFUser.objects.filter(id__in=[FindableOSFUser.objects.get(guids___id=_id).id for _id in comment._ever_mentioned]):
            comment.ever_mentioned.add(user)


def unmigrate_user_guid_array_from_m2m(state, schema):
    Comment = state.get_model('osf', 'comment')
    with disable_auto_now_fields(models=[Comment]):
        for comment in Comment.objects.exclude(ever_mentioned__isnull=False).all():
            comment._ever_mentioned = list(comment.ever_mentioned.values_list('guids___id', flat=True))
            comment.save()


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
        pp.subjects = [
            [s._id for s in hier] for hier in pp.subject_hierarchy
        ]
        pp.save()
    field.auto_now = True


def remove_invalid_social_entries(state, *args, **kwargs):
    OSFUser = state.get_model('osf', 'osfuser')
    # targets = OSFUser.objects.filter()
    targets = OSFUser.objects.exclude(social={})

    logger.info('Removing invalid social entries!')

    for user in targets:
        for invalid_key in set(user.social.keys()) - set(OSFUser.SOCIAL_FIELDS.keys()):
                logger.warn(str(dir(user)))
                user.social.pop(invalid_key)
                logger.info('User ID {0}: dropped social: {1}'.format(user.id, invalid_key))
                user.save()

    logger.info('Invalid social entry removal completed.')


def add_quickfiles(*args, **kwargs):
    ids_without_quickfiles = list(OSFUser.objects.exclude(nodes_created__type=QuickFilesNode._typedmodels_type).values_list('id', flat=True))

    users_without_quickfiles = OSFUser.objects.filter(id__in=ids_without_quickfiles).order_by('id')
    total_quickfiles_to_create = users_without_quickfiles.count()

    logger.info('About to add a QuickFilesNode for {} users.'.format(total_quickfiles_to_create))

    paginated_users = Paginator(users_without_quickfiles, 1000)

    total_created = 0
    for page_num in paginated_users.page_range:
        quickfiles_to_create = []
        for user in paginated_users.page(page_num).object_list:
            quickfiles_to_create.append(
                QuickFilesNode(
                    title=get_quickfiles_project_title(user),
                    creator=user
                )
            )
            total_created += 1

        all_quickfiles = QuickFilesNode.objects.bulk_create(quickfiles_to_create)
        logger.info('Created {}/{} QuickFilesNodes'.format(total_created, total_quickfiles_to_create))
        logger.info('Preparing to create contributors and folders')

        contributors_to_create = []
        osfs_folders_to_create = []
        for quickfiles in all_quickfiles:
            ensure_guid(QuickFilesNode, quickfiles, True)
            osfs_folders_to_create.append(
                OsfStorageFolder(provider='osfstorage', name='', node=quickfiles)
            )

            contributors_to_create.append(
                Contributor(
                    user=quickfiles.creator,
                    node=quickfiles,
                    visible=True,
                    read=True,
                    write=True,
                    admin=True,
                    _order=0
                )
            )

        Contributor.objects.bulk_create(contributors_to_create)
        OsfStorageFolder.objects.bulk_create(osfs_folders_to_create)

        logger.info('Contributors and addons folders')
        logger.info('Adding storage addons')
        osfs_to_create = []
        for folder in osfs_folders_to_create:
            osfs_to_create.append(
                OSFSNodeSettings(owner=folder.node, root_node=folder)
            )

        OSFSNodeSettings.objects.bulk_create(osfs_to_create)


def remove_quickfiles(*args, **kwargs):
    QuickFilesNode.objects.all().delete()


def update_metaschema_active(*args, **kwargs):
    MetaSchema = args[0].get_model('osf', 'metaschema')
    MetaSchema.objects.filter(schema_version__lt=2).update(active=False)


def add_reviews_notification_subscription(state, schema_editor):
    add_reviews_notification_setting('global_reviews', state=state)


# When a preprint provider is set up with a reviews/moderation workflow,
# make sure all existing preprints will be in a public state.
def accept_all_published_preprints(apps, schema_editor):
    Preprint = apps.get_model('osf', 'PreprintService')
    published_preprints = Preprint.objects.filter(is_published=True, reviews_state=DefaultStates.INITIAL.value)
    published_preprints.update(reviews_state=DefaultStates.ACCEPTED.value, date_last_transitioned=F('date_published'))


def add_preprint_doi_created(state, schema):
    """
    Sets preprint_doi_created equal to date_published for existing published preprints.
    """
    PreprintService = state.get_model('osf', 'preprintservice')
    null_preprint_doi_created = PreprintService.objects.filter(preprint_doi_created__isnull=True, date_published__isnull=False)
    preprints_count = null_preprint_doi_created.count()
    current_preprint = 0
    logger.info('{} published preprints found with preprint_doi_created is null.'.format(preprints_count))
    ContentType = state.get_model('contenttypes', 'ContentType')
    Identifier = state.get_model('osf', 'identifier')

    with disable_auto_now_fields(models=[PreprintService]):
        for preprint in null_preprint_doi_created:
            current_preprint += 1
            content_type = ContentType.objects.get_for_model(preprint)
            if Identifier.objects.filter(object_id=preprint.id, category='doi', content_type=content_type).exists():
                preprint.preprint_doi_created = preprint.date_published
                preprint.save()
                logger.info('Preprint ID {}, {}/{} preprint_doi_created field populated.'.format(preprint.id, current_preprint, preprints_count))
            else:
                logger.info('Preprint ID {}, {}/{} skipped because a DOI has not been created.'.format(preprint.id, current_preprint, preprints_count))


def reverse_func(state, schema):
    """
    Reverses data migration. Sets preprint_doi_created field back to null.
    """
    PreprintService = state.get_model('osf', 'preprintservice')
    logger.info('Reversing preprint_doi_created migration.')
    PreprintService.objects.filter(preprint_doi_created__isnull=False).update(preprint_doi_created=None)


PREMIGRATED = '1-minute-incremental-migrations' in settings.CeleryConfig.beat_schedule


def finalize_premigrated(state, schema):
    from scripts.premigrate_created_modified import finalize_migration
    logger.info('Finalizing pre-migraiton')
    finalize_migration()


def get_style_files(path):
    files = (os.path.join(path, x) for x in os.listdir(path))
    return (f for f in files if os.path.isfile(f))


def parse_citation_styles(state, schema):
    # drop all styles
    CitationStyle = state.get_model('osf', 'citationstyle')
    CitationStyle.objects.all().delete()

    for style_file in get_style_files(settings.CITATION_STYLES_PATH):
        with open(style_file, 'r') as f:
            try:
                root = etree.parse(f).getroot()
            except etree.XMLSyntaxError:
                continue

            namespace = root.nsmap.get(None)
            selector = '{{{ns}}}info/{{{ns}}}'.format(ns=namespace)

            title = root.find(selector + 'title').text
            # `has_bibliography` is set to `True` for Bluebook citation formats due to the special way we handle them.
            has_bibliography = root.find('{{{ns}}}{tag}'.format(ns=namespace, tag='bibliography')) is not None or 'Bluebook' in title
            # Required
            fields = {
                '_id': os.path.splitext(os.path.basename(style_file))[0],
                'title': title,
                'has_bibliography': has_bibliography,
            }

            # Optional
            try:
                fields['short_title'] = root.find(selector + 'title-short').text
            except AttributeError:
                pass

            try:
                fields['summary'] = root.find(selector + 'summary').text
            except AttributeError:
                pass

            style = CitationStyle(**fields)
            style.save()


def revert(state, schema):
    # The revert of this migration simply removes all CitationStyle instances.
    CitationStyle = state.get_model('osf', 'citationstyle')
    CitationStyle.objects.all().delete()


EMBER_WAFFLE_PAGES = [
    'create_draft_registration',
    'dashboard',
    'edit_draft_registration',
    'file_detail',
    'home',
    'meeting_detail',
    'meetings',
    'my_projects',
    'project_analytics',
    'project_contributors',
    'project_detail',
    'project_files',
    'project_forks',
    'project_registrations',
    'project_settings',
    'project_wiki',
    'registration_form_detail',
    'search',
    'support',
    'user_profile',
    'user_settings'
]


def reverse_func_waffles(state, schema):
    pages = [format_ember_waffle_flag_name(page) for page in EMBER_WAFFLE_PAGES]
    Flag.objects.filter(name__in=pages).delete()
    return


def format_ember_waffle_flag_name(page):
    return '{}{}{}'.format('ember_', page, '_page')


def add_ember_waffle_flags(state, schema):
    """
    This migration adds some waffle flags for pages that are being emberized.
    Waffle flags are used for feature flipping, for example, showing an
    emberized page to one set of users, and the existing osf page for another set.

    By default, flags are given an everyone=False value, which overrides all other settings,
    making the flag False for everyone.  Flag settings can be changed in the Django admin app.
    """
    for page in EMBER_WAFFLE_PAGES:
        Flag.objects.get_or_create(name=format_ember_waffle_flag_name(page), everyone=False)
    return


def set_basefilenode_target(apps, schema_editor):
    BaseFileNode = apps.get_model('osf', 'basefilenode')
    AbstractNode = apps.get_model('osf', 'abstractnode')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    target_content_type_id = ContentType.objects.get_for_model(AbstractNode).id

    BATCHSIZE = 10000

    max_pk = BaseFileNode.objects.aggregate(models.Max('pk'))['pk__max']
    if max_pk is not None:
        for offset in range(0, max_pk + 1, BATCHSIZE):
            (
                BaseFileNode.objects
                .filter(pk__gte=offset)
                .filter(pk__lt=offset + BATCHSIZE)
                .filter(target_object_id__isnull=True)
                .filter(target_content_type_id__isnull=True)
                .update(
                    target_content_type_id=target_content_type_id,
                    target_object_id=models.F('node_id')
                )
            )
            end = offset + BATCHSIZE
            percent = '{:.1f}%'.format(end / max_pk * 100)
            logger.info(
                'Updated osf_basefilenode {}-{}/{} ({})'.format(
                    offset,
                    end,
                    max_pk,
                    percent,
                )
            )


def reset_basefilenode_target_to_node(*args, **kwargs):
    sql = 'UPDATE osf_basefilenode SET node_id = target_object_id;'
    with connection.cursor() as cursor:
        cursor.execute(sql)


class GroupHelper(object):
    """ Helper for managing permission groups for a given provider during migrations.

        The mixed-in functionality from ReviewProviderMixin is unavailable during migrations
    """

    def __init__(self, provider):
        self.provider = provider

    def format_group(self, name):
        from osf.models.mixins import ReviewProviderMixin
        if name not in ReviewProviderMixin.groups:
            raise ValueError('Invalid reviews group: "{}"'.format(name))
        return ReviewProviderMixin.group_format.format(readable_type=self.provider.readable_type, id=self.provider.id, group=name)

    def get_group(self, name):
        from django.contrib.auth.models import Group
        return Group.objects.get(name=self.format_group(name))

    def update_provider_auth_groups(self):
        from osf.models.mixins import ReviewProviderMixin
        for group_name, group_permissions in ReviewProviderMixin.groups.items():
            group, created = Group.objects.get_or_create(name=self.format_group(group_name))
            to_remove = set(get_perms(group, self.provider)).difference(group_permissions)
            for p in to_remove:
                remove_perm(p, group, self.provider)
            for p in group_permissions:
                assign_perm(p, group, self.provider)


def populate_provider_notification_subscriptions(apps, schema_editor):
    NotificationSubscription = apps.get_model('osf', 'NotificationSubscription')
    PreprintProvider = apps.get_model('osf', 'PreprintProvider')
    for provider in PreprintProvider.objects.all():
        helper = GroupHelper(provider)
        try:
            provider_admins = helper.get_group('admin').user_set.all()
            provider_moderators = helper.get_group('moderator').user_set.all()
        except Group.DoesNotExist:
            logger.warn('Unable to find groups for provider "{}", assuming there are no subscriptions to create.'.format(provider._id))
            continue
        instance, created = NotificationSubscription.objects.get_or_create(_id='{provider_id}_new_pending_submissions'.format(provider_id=provider._id),
                                                                           event_name='new_pending_submissions',
                                                                           provider=provider)
        for user in provider_admins | provider_moderators:
            # add user to subscription list but set their notification to none by default
            instance.add_user_to_subscription(user, 'email_transactional', save=True)


def revert_populate_notification_subscriptions(apps, schema_editor):
    NotificationSubscription = apps.get_model('osf', 'NotificationSubscription')
    # The revert of this migration deletes all NotificationSubscription instances
    NotificationSubscription.objects.filter(provider__isnull=False).delete()


PREPRINT_DOI_NAMESPACE = {
    'osf': '10.31219',
    'agrixiv': '10.31220',
    'arabixiv': '10.31221',
    'bitss': '10.31222',
    'eartharxiv': '10.31223',
    'engrxiv': '10.31224',
    'focusarchive': '10.31225',
    'frenxiv': '10.31226',
    'inarxiv': '10.31227',
    'lawarxiv': '10.31228',
    'lissa': '10.31229',
    'marxiv': '10.31230',
    'mindrxiv': '10.31231',
    'nutrixiv': '10.31232',
    'paleorxiv': '10.31233',
    'psyarxiv': '10.31234',
    'socarxiv': '10.31235',
    'sportrxiv': '10.31236',
    'thesiscommons': '10.31237'
}


def add_doi_prefix(*args, **kwargs):
    for key, value in PREPRINT_DOI_NAMESPACE.items():
        provider = PreprintProvider.objects.filter(_id=key)
        if not provider.exists():
            logger.info('Could not find provider with _id {}, skipping for now...'.format(key))
            continue
        provider = provider.get()
        provider.doi_prefix = value
        provider.save()


osfstorage_config = apps.get_app_config('addons_osfstorage')


def add_osfstorage_addon(apps, *args):
    OSFUser = apps.get_model('osf', 'OSFUser')
    Region = apps.get_model('addons_osfstorage', 'Region')
    OsfStorageUserSettings = apps.get_model('addons_osfstorage', 'UserSettings')

    default_region, created = Region.objects.get_or_create(
        _id=DEFAULT_REGION_ID,
        name=DEFAULT_REGION_NAME,
        waterbutler_credentials=osfstorage_config.WATERBUTLER_CREDENTIALS,
        waterbutler_settings=osfstorage_config.WATERBUTLER_SETTINGS,
        waterbutler_url=WATERBUTLER_URL
    )

    if created:
        logger.info('Created default region: {}'.format(DEFAULT_REGION_NAME))

    total_users = OSFUser.objects.all().count()
    users_done = 0
    paginator = Paginator(OSFUser.objects.all().order_by('pk'), 1000)
    for page_num in paginator.page_range:
        page = paginator.page(page_num)

        user_settings_to_update = []
        for user in page:
            new_user_settings = OsfStorageUserSettings(
                owner=user,
                default_region=default_region
            )
            user_settings_to_update.append(new_user_settings)
            users_done += 1

        OsfStorageUserSettings.objects.bulk_create(user_settings_to_update)
        logger.info('Created {}/{} UserSettings'.format(users_done, total_users))

    logger.info('Created UserSettings for {} users'.format(total_users))


def remove_osfstorage_addon(apps, *args):
    Region = apps.get_model('addons_osfstorage', 'Region')
    OsfStorageUserSettings = osfstorage_config.user_settings

    region = Region.objects.filter(
        name=DEFAULT_REGION_NAME
    )

    if region:
        region.get().delete()

    OsfStorageUserSettings.objects.all().delete()


def revert_citation_style(state, schema):
    # The revert of this migration simply removes all CitationStyle instances.
    CitationStyle = state.get_model('osf', 'citationstyle')
    CitationStyle.objects.all().delete()


def update_comment_root_target(state, *args, **kwargs):
    Comment = state.get_model('osf', 'comment')
    comments = Comment.objects.exclude(is_deleted=True).select_related('root_target')
    logger.info('{} comments to check'.format(comments.count()))
    comments_to_update = []
    for comment in comments:
        if comment.root_target:
            root_target_ctype = comment.root_target.content_type
            root_target_model_cls = state.get_model(root_target_ctype.app_label, root_target_ctype.model)
            root_target = root_target_model_cls.objects.get(pk=comment.root_target.object_id)
            if hasattr(root_target, 'is_deleted') and root_target.is_deleted:
                logger.info('{} is deleted. Setting Comment {} root_target to None'.format(root_target, comment.pk))
                comment.root_target = None
                comments_to_update.append(comment)
            if hasattr(root_target, 'deleted') and root_target.deleted:
                logger.info('{} is deleted. Setting Comment {} root_target to None'.format(root_target, comment.pk))
                comment.root_target = None
                comments_to_update.append(comment)
    bulk_update(comments_to_update, update_fields=['root_target'])
    logger.info('Total comments migrated: {}'.format(len(comments_to_update)))


update_subject_sql = """
            UPDATE osf_subject
            SET provider_id = (SELECT id FROM osf_preprintprovider WHERE _id = 'osf');
            """


reverse_update_subject_sql = """
            UPDATE osf_subject
            SET provider_id = NULL;
            """

def post_migrate_signal(state, schema):
    # this is to make sure that the draft registration permissions created earlier exist!
    emit_post_migrate_signal(3, False, 'default')


def clear_draft_registration_responses(state, schema):
    """
    Reverse migration
    """
    DraftRegistration = state.get_model('osf', 'draftregistration')
    DraftRegistration.objects.update(
        registration_responses={},
        registration_responses_migrated=False
    )

def clear_registration_responses(state, schema):
    """
    Reverse migration
    """
    Registration = state.get_model('osf', 'registration')
    Registration.objects.update(
        registration_responses={},
        registration_responses_migrated=False
    )

def migrate_draft_registration_metadata(state, schema):
    migrate_draft_registrations(
        dry_run=False,
        rows='all',
        DraftRegistrationModel=state.get_model('osf', 'draftregistration')
    )

def migrate_registration_registered_meta(state, schema):
    migrate_registrations(
        dry_run=False,
        rows='all',
        AbstractNodeModel=state.get_model('osf', 'abstractnode')
    )


def remove_version_1_schemas(state, schema):
    RegistrationSchema = state.get_model('osf', 'registrationschema')
    assert RegistrationSchema.objects.filter(schema_version=1, abstractnode__isnull=False).count() == 0
    assert RegistrationSchema.objects.filter(schema_version=1, draftregistration__isnull=False).count() == 0
    RegistrationSchema.objects.filter(schema_version=1).delete()


def update_schemaless_registrations(state, schema):
    RegistrationSchema = state.get_model('osf', 'registrationschema')
    AbstractNode = state.get_model('osf', 'abstractnode')

    open_ended_schema = RegistrationSchema.objects.get(name='Open-Ended Registration', schema_version=2)
    open_ended_meta = {
        '{}'.format(open_ended_schema._id): {
            'summary': {
                'comments': [],
                'extra': [],
                'value': ''
            }
        }
    }

    schemaless_regs_with_meta = AbstractNode.objects.filter(type='osf.registration', registered_schema__isnull=True).exclude(registered_meta={})
    schemaless_regs_without_meta = AbstractNode.objects.filter(type='osf.registration', registered_schema__isnull=True, registered_meta={})

    for reg in schemaless_regs_without_meta.all():
        reg.registered_schema.add(open_ended_schema)
        reg.registered_meta = open_ended_meta
        reg.save()

    for reg in schemaless_regs_with_meta.all():
        reg.registered_schema.add(RegistrationSchema.objects.get(_id=reg.registered_meta.keys()[0]))


def update_schema_configs(state, schema):
    RegistrationSchema = state.get_model('osf', 'registrationschema')
    for rs in RegistrationSchema.objects.all():
        if rs.schema.get('description', False):
            rs.description = rs.schema['description']
        if rs.schema.get('config', False):
            rs.config = rs.schema['config']
        rs.save()


def unset_schema_configs(state, schema):
    RegistrationSchema = state.get_model('osf', 'registrationschema')
    RegistrationSchema.objects.update(
        config=dict(),
        description='',
    )


def restore_default_through_table(state, schema):
    sql = """
        DROP TABLE osf_basefilenode_versions;
        CREATE TABLE osf_basefilenode_versions AS
        SELECT
            new_thru.basefilenode_id,
            new_thru.fileversion_id
        FROM
            osf_basefileversionsthrough AS new_thru;

        ALTER TABLE osf_basefilenode_versions ADD COLUMN id SERIAL PRIMARY KEY;
        ALTER TABLE osf_basefilenode_versions ADD CONSTRAINT osf_basefilenod_basefilenode_id_b0knah27_fk_osf_basefilenode_id FOREIGN KEY (basefilenode_id) REFERENCES osf_basefilenode DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE osf_basefilenode_versions ALTER COLUMN basefilenode_id
        SET
            DATA TYPE INTEGER;
        ALTER TABLE osf_basefilenode_versions ALTER COLUMN fileversion_id
        SET
            NOT NULL;
        ALTER TABLE osf_basefilenode_versions ALTER COLUMN fileversion_id
        SET
            DATA TYPE INTEGER;
        ALTER TABLE osf_basefilenode_versions ALTER COLUMN basefilenode_id
        SET
            NOT NULL;
        ALTER TABLE osf_basefilenode_versions ADD CONSTRAINT osf_basefilenode__fileversion_id_93etanfc_fk_osf_fileversion_id FOREIGN KEY (fileversion_id) REFERENCES osf_fileversion DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE osf_basefilenode_versions ADD CONSTRAINT osf_basefilenode__fileversion_uniq564 UNIQUE (basefilenode_id, fileversion_id);
        CREATE INDEX
        ON osf_basefilenode_versions (basefilenode_id, fileversion_id);
        CREATE INDEX
        ON osf_basefilenode_versions (basefilenode_id);
        CREATE INDEX
        ON osf_basefilenode_versions (fileversion_id);
    """
    with connection.cursor() as cursor:
        cursor.execute(sql)


def populate_fileversion_name(state, schema):

    sql = """
        DROP TABLE osf_basefileversionsthrough;
        CREATE TABLE osf_basefileversionsthrough AS
        SELECT
            obfv.basefilenode_id,
            obfv.fileversion_id,
            ob.name as version_name
        FROM
            osf_basefilenode_versions obfv
            LEFT JOIN
                osf_basefilenode ob
                ON obfv.basefilenode_id = ob.id;
        ALTER TABLE osf_basefileversionsthrough ADD COLUMN id SERIAL PRIMARY KEY;
        ALTER TABLE osf_basefileversionsthrough ADD CONSTRAINT osf_basefilenod_basefilenode_id_b0nwad27_fk_osf_basefilenode_id FOREIGN KEY (basefilenode_id) REFERENCES osf_basefilenode DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE osf_basefileversionsthrough ALTER COLUMN basefilenode_id
        SET
            DATA TYPE INTEGER;
        ALTER TABLE osf_basefileversionsthrough ALTER COLUMN fileversion_id
        SET
            NOT NULL;
        ALTER TABLE osf_basefileversionsthrough ALTER COLUMN fileversion_id
        SET
            DATA TYPE INTEGER;
        ALTER TABLE osf_basefileversionsthrough ALTER COLUMN basefilenode_id
        SET
            NOT NULL;
        ALTER TABLE osf_basefileversionsthrough ADD CONSTRAINT osf_basefilenode__fileversion_id_93nwadfc_fk_osf_fileversion_id FOREIGN KEY (fileversion_id) REFERENCES osf_fileversion DEFERRABLE INITIALLY DEFERRED;
        ALTER TABLE osf_basefileversionsthrough ADD CONSTRAINT osf_basefilenode__fileversion_uniq UNIQUE (basefilenode_id, fileversion_id);
        CREATE INDEX
        ON osf_basefileversionsthrough (basefilenode_id, fileversion_id);
        CREATE INDEX
        ON osf_basefileversionsthrough (basefilenode_id);
        CREATE INDEX
        ON osf_basefileversionsthrough (fileversion_id);
    """

    with connection.cursor() as cursor:
        cursor.execute(sql)

old_scope_mapping = {
    'osf.users.all_read': 'osf.users.profile_read',
    'osf.users.all_write': 'osf.users.profile_write',
    'osf.nodes.all_read': 'osf.nodes.full_read',
    'osf.nodes.all_write': 'osf.nodes.full_write'
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
            loaded_scope = ApiOAuth2Scope.objects.get(name=old_scope_mapping.get(scope, scope))
            token.scopes_temp.add(loaded_scope)
            token.save()


def add_registration_files_count(state, *args, **kwargs):
    """
    Caches registration files count on Registration object.
    Importing Registration model outside of this method to take advantage of files
    relationship for speed purposes in this migration.  If this model changes significantly,
    this migration may have to be modified in the future so it runs on an empty db.
    """
    Registration = state.get_model('osf', 'registration')
    registrations = Registration.objects.filter(is_deleted=False, files_count__isnull=True)
    BaseFileNode = state.get_model('osf', 'BaseFileNode')
    ContentType = state.get_model('contenttypes', 'ContentType')
    content_type = ContentType.objects.get(app_label='osf', model='abstractnode')
    registrations_to_update = []

    for registration in registrations:
        registration_files = BaseFileNode.objects.filter(
            target_object_id=registration.id,
            target_content_type=content_type,
            type='osf.osfstoragefile',
            deleted_on__isnull=True,
        )
        registration.files_count = registration_files.count()
        registrations_to_update.append(registration)

    bulk_update(registrations_to_update, update_fields=['files_count'], batch_size=5000)
    logger.info('Populated `files_count` on a total of {} registrations'.format(len(registrations_to_update)))


TAG_MAP = {
    'spam_flagged': SpamStatus.FLAGGED,
    'spam_confirmed': SpamStatus.SPAM,
    'ham_confirmed': SpamStatus.HAM
}


def add_spam_status_to_tagged_users(state, schema):
    OSFUser = state.get_model('osf', 'osfuser')
    users_with_tag = OSFUser.objects.filter(tags__name__in=TAG_MAP.keys()).prefetch_related('tags')
    users_to_update = []
    for user in users_with_tag:
        for tag, value in TAG_MAP.items():
            if user.tags.filter(system=True, name=tag).exists():
                user.spam_status = value
        users_to_update.append(user)
    bulk_update(users_to_update, update_fields=['spam_status'])


def remove_spam_status_from_tagged_users(state, schema):
    OSFUser = state.get_model('osf', 'osfuser')
    users_with_tag = OSFUser.objects.filter(tags__name__in=TAG_MAP.keys())
    users_with_tag.update(spam_status=None)


def forward(state, *args, **kwargs):
    """
    For every conference, fetches all AbstractNodes with a case-insensitive matching Tag
    to the conference endpoint.  Adds these nodes to conference.submissions.
    """
    Conference = state.get_model('osf', 'Conference')
    AbstractNode = state.get_model('osf', 'AbstractNode')
    Tag = state.get_model('osf', 'Tag')

    # Small number of conferences
    for conference in Conference.objects.all():
        tags = Tag.objects.filter(system=False, name__iexact=conference.endpoint).values_list('pk', flat=True)
        # Not restricting on public/deleted here, just adding all nodes with meeting tags
        # and then API will restrict to only public, non-deleted nodes
        for node in AbstractNode.objects.filter(tags__in=tags):
            conference.submissions.add(node)
    logger.info('Finished adding submissions to conferences.')


def backward(state, *args, **kwargs):
    Conference = state.get_model('osf', 'Conference')
    for conference in Conference.objects.all():
        for submission in conference.submissions.all():
            conference.submissions.remove(submission)
    logger.info('Finished clearing submissions from conferences.')


increment = 100000

"""
PREPRINT MIGRATION (we were already using guardian for preprints, but weren't using direct foreign keys)
1) For each guardian GroupObjectPermission table entry that is related to a preprint, add entry to the
PreprintGroupObjectPermission table
"""

# DELETE FROM guardian_groupobjectpermission present in both forward and reverse migrations because forward migration had already been
# completed on staging environment and reverse migration needed to delete old rows before restoring out of the box guardian rows
def reverse_migrate_preprints(state, schema):
    sql = """
        DELETE FROM guardian_groupobjectpermission GO
        USING django_content_type CT
        WHERE CT.model = 'preprint' AND CT.app_label = 'osf'
        AND GO.content_type_id = CT.id;

        -- Reverse migration - Repopulating out of the box guardian table
        INSERT INTO guardian_groupobjectpermission (object_pk, content_type_id, group_id, permission_id)
        SELECT CAST(PG.content_object_id AS INT), CAST(CT.id AS INT), CAST(PG.group_id AS INT), CAST(PG.permission_id AS INT)
        FROM osf_preprintgroupobjectpermission PG, django_content_type CT
        WHERE CT.model = 'preprint' AND CT.app_label = 'osf';

        -- Reverse migration - dropping custom PreprintGroupObject permission table
        DELETE FROM osf_preprintgroupobjectpermission;
        """

    with connection.cursor() as cursor:
        cursor.execute(sql)

# Forward migration - moving preprints to dfks
def migrate_preprints_to_direct_fks(state, schema):
    GroupObjectPermission = state.get_model('guardian', 'groupobjectpermission')
    ContentType = state.get_model('contenttypes', 'ContentType')

    Preprint = state.get_model('osf', 'preprint')
    preprint_ct_id = ContentType.objects.get_for_model(Preprint).id
    max_pid = getattr(GroupObjectPermission.objects.filter(content_type_id=preprint_ct_id).last(), 'id', 0)

    total_pages = int(ceil(max_pid / float(increment)))
    page_start = 0
    page_end = 0
    page = 0

    logger.info('{}'.format('Migrating preprints to use direct foreign keys to speed up permission checks.'))
    while page_end <= (max_pid):
        page += 1
        page_end += increment
        if page <= total_pages:
            logger.info('Updating page {} / {}'.format(page_end / increment, total_pages))

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO osf_preprintgroupobjectpermission (content_object_id, group_id, permission_id)
                SELECT CAST(GO.object_pk AS INT), CAST(GO.group_id AS INT), CAST(GO.permission_id AS INT)
                FROM guardian_groupobjectpermission GO, django_content_type CT
                WHERE CT.model = 'preprint' AND CT.app_label = 'osf'
                AND GO.content_type_id = CT.id
                AND CAST(GO.object_pk AS INT) > %s
                AND CAST(GO.object_pk AS INT) <= %s;

                DELETE FROM guardian_groupobjectpermission GO
                USING django_content_type CT
                WHERE CT.model = 'preprint' AND CT.app_label = 'osf'
                AND GO.content_type_id = CT.id
                AND CAST(GO.object_pk AS INT) > %s
                AND CAST(GO.object_pk AS INT) <= %s;
            """ % (page_start, page_end, page_start, page_end)
            )
        page_start = page_end
    logger.info('Finished preprint direct foreign key migration.')
