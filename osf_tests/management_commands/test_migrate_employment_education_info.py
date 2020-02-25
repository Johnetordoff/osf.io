# encoding: utf-8
import pytest

from django_test_migrations.contrib.unittest_case import MigratorTestCase

@pytest.mark.django_db
class TestEducationEmploymentInfoMigration(MigratorTestCase):
    """This class is used to test direct migrations."""

    migrate_from = ('osf', '0200_auto_20200214_1518')
    migrate_to = ('osf', '0202_auto_20200225_1540')

    def prepare(self):
        """Prepare some data before the migration."""

        old_style_user = self.old_state.apps.get_model('osf', 'OSFUser')
        user = old_style_user(
            username='bdawk@iggles.bird',
            fullname='Brian Dawkins',
            password='morexmanthenthenextman'
        )
        schools = [
            {
                'degree': 'BA Communications',
                'department': 'Communications',
                'endMonth': None,
                'endYear': 1996,
                'institution': 'Clemson',
                'ongoing': False,
                'startMonth': None,
                'startYear': 1973
            }
        ]
        jobs = [
            {
                'title': 'Safety',
                'department': 'Defense',
                'endMonth': None,
                'endYear': 2008,
                'institution': 'Philadelphia Eagles',
                'ongoing': False,
                'startMonth': None,
                'startYear': 1996
            }, {
                'title': 'Hall of Fame Safety',
                'department': 'Defense',
                'institution': 'Philadelphia Eagles',
                'ongoing': True,
                'startYear': 2018
            }
        ]
        user.jobs = jobs
        user.schools = schools
        user.save()
        self.user = user

    def test_migration(self):
        """Run the test itself."""
        OSFUser = self.new_state.apps.get_model('osf', 'OSFUser')

        user = OSFUser.objects.get(username=self.user.username)

        assert user.education.all().count() == 1
        education = user.education.first()

        assert education.institution == 'Clemson'

        assert user.employment.all().count() == 2
        titles = user.employment.values_list('title', flat=True)
        assert ['Safety', 'Hall of Fame Safety'] == list(titles)

        assert education.institution == 'Clemson'

        assert not hasattr(OSFUser, 'jobs')
        assert not hasattr(OSFUser, 'schools')
