import pytest
from osf_tests.factories import WithdrawnRegistrationFactory

from osf.models import TrashedFileNode
from osf.management.commands.purge_files import (
    mark_withdrawn_files_as_deleted,
    purge_deleted_withdrawn_files,
    mark_failed_registration_files_as_deleted,
    purge_deleted_failed_registration_files
)
from website.settings import PURGE_DELTA, ARCHIVE_TIMEOUT_TIMEDELTA
from addons.osfstorage import settings as addon_settings
from osf_tests.factories import RegistrationFactory
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestPurgedFiles:

    @pytest.fixture()
    def withdrawn_registration(self):
        retraction = WithdrawnRegistrationFactory()
        registration = retraction.target_registration
        return registration

    @pytest.fixture()
    def stuck_registration(self):
        registration = RegistrationFactory(archive=True)
        # Make the registration "stuck"
        archive_job = registration.archive_job
        archive_job.datetime_initiated = (timezone.now() - ARCHIVE_TIMEOUT_TIMEDELTA - timedelta(hours=1))
        archive_job.save()
        return registration

    @pytest.fixture
    def stuck_file(self, stuck_registration):
        file = stuck_registration.get_addon('osfstorage').root_node.append_file('Hurts')
        file.create_version(
            stuck_registration.creator,
            {
                u'service': u'Fulgham',
                addon_settings.WATERBUTLER_RESOURCE: u'osf',
                u'object': u'Sanders',
                u'bucket': u'Hurts',
            }, {
                u'size': 1234,
                u'contentType': u'text/plain'
            })
        file.save()
        return file

    @pytest.fixture
    def withdrawn_file(self, withdrawn_registration):
        file = withdrawn_registration.get_addon('osfstorage').root_node.append_file('Hurts')
        file.create_version(
            withdrawn_registration.creator,
            {
                u'service': u'Fulgham',
                addon_settings.WATERBUTLER_RESOURCE: u'osf',
                u'object': u'Sanders',
                u'bucket': u'Hurts',
            }, {
                u'size': 1234,
                u'contentType': u'text/plain'
            })
        file.save()
        return file

    def test_withdrawn_registration_files(self, mock_gcs, withdrawn_registration, withdrawn_file):
        # Marks files as deleted
        assert withdrawn_registration.files.filter(deleted__isnull=True).count() == 1
        mark_withdrawn_files_as_deleted(dry_run=False)
        assert withdrawn_registration.files.filter(deleted__isnull=True).count() == 0

        # Files are purged PURGE_DETLA time after they are deleted
        trashed_file = TrashedFileNode.objects.first()
        trashed_file.deleted -= PURGE_DELTA
        trashed_file.save()

        purge_deleted_withdrawn_files()

        # assert bucket was called with the passed string
        bucket = mock_gcs().get_bucket
        bucket.assert_called_with('Hurts')

        # assert blob and upload were called with expected params
        blob = bucket('Hurts').get_blob
        blob.assert_called_with('Sanders')

    def test_failed_registration_files(self, mock_gcs, stuck_registration, stuck_file):
        # Marks files as deleted
        assert stuck_registration.files.filter(deleted__isnull=True).count() == 1
        mark_failed_registration_files_as_deleted(dry_run=False)
        assert stuck_registration.files.filter(deleted__isnull=True).count() == 0

        # Files are purged PURGE_DETLA time after they are deleted
        trashed_file = TrashedFileNode.objects.first()
        trashed_file.deleted -= PURGE_DELTA
        trashed_file.save()

        purge_deleted_failed_registration_files()

        # assert bucket was called with the passed string
        bucket = mock_gcs().get_bucket
        bucket.assert_called_with('Hurts')

        # assert blob and upload were called with expected params
        blob = bucket('Hurts').get_blob
        blob.assert_called_with('Sanders')
