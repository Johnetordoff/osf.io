from osf.utils.testing.pytest_utils import MigrationTestCase
from osf.quickfiles.migration_utils import create_quickfolders, migrate_quickfiles_to_quickfolders

from osf_tests.factories import AuthUserFactory
from osf.models import OSFUser, QuickFolder
from addons.osfstorage.models import OsfStorageFile

qs2set = lambda x: set(list(x))


class TestQuickFilesMigration(MigrationTestCase):
    number_of_users = 10

    def test_create_quickfolders(self):
        self.bulk_add(self.number_of_users, AuthUserFactory, with_quickfiles_node=True)

        #sanity check
        assert OSFUser.objects.all().count() == self.number_of_users

        create_quickfolders()

        assert QuickFolder.objects.all().count() == self.number_of_users

        quickfolder_target_ids = qs2set(QuickFolder.objects.all().values_list('target_object_id', flat=True))
        user_ids = qs2set(OSFUser.objects.all().values_list('id', flat=True))

        assert quickfolder_target_ids == user_ids

        #sanity check
        #assert OSFUser.objects.all().count() == self.number_of_users
        #assert QuickFolder.objects.all().count() == self.number_of_users

        migrate_quickfiles_to_quickfolders()

        assert OsfStorageFile.objects.all().count() == self.number_of_users
