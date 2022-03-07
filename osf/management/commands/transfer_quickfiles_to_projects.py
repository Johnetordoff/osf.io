import pytz
import math
import logging
import datetime

from django.db import transaction
from django.core.management.base import BaseCommand

from osf.models import (
    OSFUser,
    QuickFilesNode,
    NodeLog,
    AbstractNode,
    Guid
)

from osf.models.base import generate_guid
from osf.models.quickfiles import get_quickfiles_project_title
from osf.models.queued_mail import QueuedMail

from addons.osfstorage.models import OsfStorageFile
from website import mails, settings
from django.contrib.contenttypes.models import ContentType

logger = logging.getLogger(__name__)
QUICKFILES_DESC = 'The Quick Files feature was discontinued and it’s files were migrated into this Project on March' \
                  ' 11, 2022. The file URL’s will still resolve properly, and the Quick Files logs are available in' \
                  ' the Project’s Recent Activity.'
QUICKFILES_DATE = datetime.datetime(2022, 3, 11, tzinfo=pytz.utc)


def remove_quickfiles(dry_run=False, page_size=1000):
    with transaction.atomic():
        quick_files_ids = QuickFilesNode.objects.values_list('id', flat=True)
        quick_files_node_with_files_ids = OsfStorageFile.objects.filter(
            target_object_id__in=quick_files_ids,
            target_content_type=ContentType.objects.get_for_model(AbstractNode)
        ).values_list(
            'target_object_id',
            flat=True
        )

        logger.info(f'{quick_files_node_with_files_ids.count()} quickfiles with files were selected')

        quick_files_nodes = AbstractNode.objects.filter(
            id__in=quick_files_node_with_files_ids,
        ).order_by('pk')

        result = Guid.objects.filter(
            id__in=quick_files_nodes.values_list('guids__id', flat=True)
        ).delete()

        logger.info(f'Return value of deleted guids: {result}')


        # generate unique guids prior to record creation to avoid collisions.
        guids = set([])
        num_of_guids_needed = quick_files_node_with_files_ids.count()
        while len(guids) < num_of_guids_needed:
            guids.add(generate_guid())
        guids = list(guids)

        logger.info(f'{len(guids)} Guid ids generated')

        guids = [
            Guid(
                _id=_id,
                object_id=node,
                content_type=ContentType.objects.get_for_model(AbstractNode)
            ) for _id, node in zip(guids, quick_files_node_with_files_ids)
        ]
        Guid.objects.bulk_create(guids)
        logger.info(f'{len(guids)} Guids created')

        node_logs = [
            NodeLog(
                node=node,
                user=node.creator,
                original_node=node,
                params={'node': node._id},
                action=NodeLog.MIGRATED_QUICK_FILES
            ) for node in quick_files_nodes
        ]
        NodeLog.objects.bulk_create(node_logs)
        logger.info(f'{len(node_logs)} Node logs created')

        queued_mail = [
            QueuedMail(
                user=node.creator,
                to_addr=node.creator.email,
                send_at=QUICKFILES_DATE,
                email_type=mails.QUICKFILES_MIGRATED.tpl_prefix,
                data=dict(
                    osf_support_email=settings.OSF_SUPPORT_EMAIL,
                    can_change_preferences=False,
                    quickfiles_link=node.absolute_url
                )
            ) for node in quick_files_nodes
        ]
        QueuedMail.objects.bulk_create(queued_mail)
        logger.info(f'{len(queued_mail)} messages queued.')

        for i, node in enumerate(quick_files_nodes):
            # update guid in logs
            for log in node.logs.all():
                log.params['node'] = node._id
                log.save()

            if i and not i % page_size:
                logger.info(f'{i} had their logs updated at {datetime.datetime.now()}')

        result = quick_files_nodes.update(description=QUICKFILES_DESC, type='osf.node')
        logger.info(f'{result} quickfiles were updated to become projects.')
        if dry_run:
            raise RuntimeError('Dry run complete, rolling back.')


def reverse_remove_quickfiles(dry_run=False):
    with transaction.atomic():
        quickfiles_nodes_with_files = Node.objects.filter(
            logs__action=NodeLog.MIGRATED_QUICK_FILES
        )
        for node in quickfiles_nodes_with_files:
            node.guids.all().delete()
            node.save()

        quickfiles_nodes_with_files.update(
            type='osf.quickfilesnode',
            is_deleted=False,
            deleted=None,
        )

        users_without_nodes = OSFUser.objects.exclude(
            id__in=QuickFilesNode.objects.all().values_list(
                'creator__id',
                flat=True
            )
        )
        quickfiles_created = []
        for user in users_without_nodes:
            quickfiles_created.append(
                QuickFilesNode(
                    title=get_quickfiles_project_title(user),
                    creator=user
                )
            )

        QuickFilesNode.objects.bulk_create(quickfiles_created)

        for quickfiles in quickfiles_created:
            quickfiles.add_addon('osfstorage', auth=None, log=False)
            quickfiles.save()

        NodeLog.objects.filter(action=NodeLog.MIGRATED_QUICK_FILES).delete()
        logger.info(f'{len(QuickFilesNode.objects.all())} quickfiles were restored.')
        if dry_run:
            raise RuntimeError('Dry run complete, rolling back.')


class Command(BaseCommand):
    """
    Puts all Quickfiles into projects or reverses the effect.
    """
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--dry',
            action='store_true',
            dest='dry_run',
            help='Run migration and roll back changes to db',
            required=False,
        )
        parser.add_argument(
            '--reverse',
            type=bool,
            help='is the reverse to be run?.',
            required=False,
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        reverse = options.get('reverse', False)
        if reverse:
            reverse_remove_quickfiles(dry_run)
        else:
            remove_quickfiles(dry_run)
