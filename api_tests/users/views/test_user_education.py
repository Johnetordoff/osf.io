import pytest

from api.base.settings import API_BASE
from osf_tests.factories import EducationFactory
from api_tests.users.views.user_profile_test_mixin import (
    UserProfileListMixin, UserProfileDetailMixin, UserProfileCreateMixin,
    UserProfileUpdateMixin, UserProfileRelationshipMixin)


class UserEducationMixin:

    @pytest.fixture
    def resource_factory(self):
        return EducationFactory

    @pytest.fixture()
    def profile_type(self):
        return 'education'


@pytest.mark.django_db
class TestUserEducationList(UserEducationMixin, UserProfileListMixin):

    @pytest.fixture
    def list_url(self, user, profile_type):
        return '/{}users/{}/{}/'.format(API_BASE, user._id, profile_type)


@pytest.mark.django_db
class TestEducationDetail(UserEducationMixin, UserProfileDetailMixin):

    @pytest.fixture
    def detail_url(self, user, profile_item_one, profile_type):
        return '/{}users/{}/{}/{}/'.format(API_BASE, user._id, profile_type, profile_item_one._id)


@pytest.mark.django_db
class TestUerEducationCreate(UserEducationMixin, UserProfileCreateMixin):

    @pytest.fixture
    def list_url(self, user, profile_type):
        return '/{}users/{}/{}/'.format(API_BASE, user._id, profile_type)


@pytest.mark.django_db
class TestUserEducationUpdate(UserEducationMixin, UserProfileUpdateMixin):

    @pytest.fixture
    def detail_url(self, user, profile_item_one, profile_type):
        return '/{}users/{}/{}/{}/'.format(API_BASE, user._id, profile_type, profile_item_one._id)


@pytest.mark.django_db
class TestUserEducationRelationship(UserEducationMixin, UserProfileRelationshipMixin):

    @pytest.fixture()
    def url(self, user, profile_type):
        return '/{}users/{}/relationships/{}/'.format(API_BASE, user._id, profile_type)
