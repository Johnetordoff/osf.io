from osf.models import OSFUser
from osf.quickfiles.legacy_quickfiles import QuickFilesNode
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.apps import apps


def _create_quickfiles(instance):
    QuickFolder = apps.get_model('osf', 'QuickFolder')
    quickfiles = QuickFolder(target=instance, provider=QuickFolder._provider, path='/')
    quickfiles.save()


@receiver(post_save, sender=OSFUser)
def create_quickfiles(sender, instance, created, **kwargs):
    if created:
        _create_quickfiles(instance)


def _create_quickfiles_project(instance):
    QuickFilesNode.objects.create_for_user(instance)


def create_quickfiles_project(sender, instance, created, **kwargs):
    if created:
        _create_quickfiles_project(instance)
