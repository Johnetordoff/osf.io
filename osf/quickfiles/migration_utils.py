from osf.models import QuickFolder, OSFUser
from osf.quickfiles.legacy_quickfiles import QuickFilesNode
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Count
from django.contrib.contenttypes.models import ContentType

import logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def create_quickfolders():
    users = OSFUser.objects.all()
    user_content_type_id = ContentType.objects.get_for_model(OSFUser).id

    paginated_users = Paginator(users, 1000)

    total_created = 0
    for page_num in paginated_users.page_range:
        quickfolders_to_create = []
        for user in paginated_users.page(page_num).object_list:
            quickfolders_to_create.append(
                QuickFolder(target_object_id=user.id, target_content_type_id=user_content_type_id,
                            provider='osfstorage', path='/')
            )
            total_created += 1

    logger.info('There are {} total quickfolders created'.format(total_created))
    QuickFolder.objects.bulk_create(quickfolders_to_create)


def migrate_quickfiles_to_quickfolders(*args, **kwargs):

    user_content_type_id = ContentType.objects.get_for_model(OSFUser).id

    find_quickfolders = Subquery(QuickFolder.objects.filter(target_object_id=OuterRef('id')).values('id'))
    users_ids_for_with_quickfiles = QuickFilesNode.objects.all().annotate(file_count=Count('files')).filter(file_count__gt=1).values_list('creator_id', flat=True)
    users_with_quickfiles = OSFUser.objects.filter(id__in=users_ids_for_with_quickfiles).annotate(_quickfolder=find_quickfolders)

    for user in users_with_quickfiles:
        quickfiles_node = QuickFilesNode.objects.get_for_user(user)
        try:
            QuickFilesNode.objects.get_for_user(user).files.update(parent_id=user._quickfolder,
                                                                   target_object_id=user.id,
                                                                   target_content_type_id=user_content_type_id)
        except QuickFilesNode.DoesNotExist as exc:
            logger.info('OSFUser {} does not have quickfiles')
            raise exc
        guid = quickfiles_node.guids.last()
        guid.referent = user._quickfolder
        guid.save()
