import pytest

from framework.auth import Auth

from api_tests.subjects.mixins import UpdateSubjectsMixin
from osf_tests.factories import PreprintFactory
from osf.utils.permissions import READ


@pytest.mark.django_db
class TestPreprintUpdateSubjects(UpdateSubjectsMixin):
    @pytest.fixture()
    def resource(self, user_admin_contrib, user_write_contrib, user_read_contrib):
        preprint = PreprintFactory(creator=user_admin_contrib, is_published=True)
        preprint.add_contributor(user_write_contrib, auth=Auth(user_admin_contrib))
        preprint.add_contributor(user_read_contrib, auth=Auth(user_admin_contrib), permissions=READ)
        preprint.save()
        return preprint
