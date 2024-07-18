import mock
import pytest

from django.utils import timezone

from api.base.settings.defaults import API_BASE
from api_tests.preprints.filters.test_filters import PreprintsListFilteringMixin
from api_tests.subjects.mixins import SubjectsFilterMixin
from api_tests.reviews.mixins.filter_mixins import ReviewableFilterMixin
from osf.utils.permissions import READ
from osf_tests.factories import (
    AuthUserFactory,
    PreprintFactory,
    PreprintProviderFactory,
    ProjectFactory,
)


@pytest.mark.django_db
class TestPreprintsListFiltering(PreprintsListFilteringMixin):

    @pytest.fixture()
    def user(self):
        return AuthUserFactory()

    @pytest.fixture()
    def provider_one(self):
        return PreprintProviderFactory(name='Sockarxiv')

    @pytest.fixture()
    def provider_two(self):
        return PreprintProviderFactory(name='Piratearxiv')

    @pytest.fixture()
    def provider_three(self, provider_one):
        return provider_one

    @pytest.fixture()
    def project_one(self, user):
        return ProjectFactory(creator=user)

    @pytest.fixture()
    def project_two(self, user):
        return ProjectFactory(creator=user)

    @pytest.fixture()
    def project_three(self, user):
        return ProjectFactory(creator=user)

    @pytest.fixture()
    def url(self):
        return '/{}preprints/?version=2.2&'.format(API_BASE)

    @mock.patch('website.identifiers.clients.crossref.CrossRefClient.update_identifier')
    def test_provider_filter_equals_returns_one(self, mock_change_identifier, app, user, provider_two, preprint_two, provider_url):
        expected = [preprint_two._id]
        res = app.get('{}{}'.format(provider_url, provider_two._id), auth=user.auth)
        actual = [preprint['id'] for preprint in res.json['data']]
        assert expected == actual

    def test_filter_withdrawn_preprint(self, app, url, user):
        preprint_one = PreprintFactory(is_published=False, creator=user)
        preprint_one.date_withdrawn = timezone.now()
        preprint_one.is_public = True
        preprint_one.is_published = True
        preprint_one.date_published = timezone.now()
        preprint_one.machine_state = 'accepted'
        assert preprint_one.ever_public is False
        preprint_one.save()

        preprint_two = PreprintFactory(creator=user)
        preprint_two.date_withdrawn = timezone.now()
        preprint_two.ever_public = True
        preprint_two.save()

        expected = [preprint_two._id]
        res = app.get(url)
        actual = [preprint['id'] for preprint in res.json['data']]
        assert set(expected) == set(actual)

        user2 = AuthUserFactory()
        expected = [preprint_two._id]
        res = app.get(url, auth=user2.auth)
        actual = [preprint['id'] for preprint in res.json['data']]
        assert set(expected) == set(actual)

        preprint_one.add_contributor(user2, READ)
        preprint_two.add_contributor(user2, READ)
        expected = [preprint_two._id]
        res = app.get(url, auth=user2.auth)
        actual = [preprint['id'] for preprint in res.json['data']]
        assert set(expected) == set(actual)

        res = app.get(url, auth=user.auth)
        actual = [preprint['id'] for preprint in res.json['data']]
        assert set(expected) == set(actual)

@pytest.mark.django_db
class TestPreprintSubjectFiltering(SubjectsFilterMixin):
    @pytest.fixture()
    def resource(self, user):
        return PreprintFactory(creator=user)

    @pytest.fixture()
    def resource_two(self, user):
        return PreprintFactory(creator=user)

    @pytest.fixture()
    def url(self):
        return '/{}preprints/'.format(API_BASE)

@pytest.mark.django_db
class TestPreprintListFilteringByReviewableFields(ReviewableFilterMixin):
    @pytest.fixture()
    def url(self):
        return '/{}preprints/'.format(API_BASE)

    @pytest.fixture()
    def expected_reviewables(self, user):
        with mock.patch('website.identifiers.utils.request_identifiers'):
            preprints = [
                PreprintFactory(is_published=False, project=ProjectFactory(is_public=True)),
                PreprintFactory(is_published=False, project=ProjectFactory(is_public=True)),
                PreprintFactory(is_published=False, project=ProjectFactory(is_public=True)),
            ]
            preprints[0].run_submit(user)
            preprints[0].run_accept(user, 'comment')
            preprints[1].run_submit(user)
            preprints[1].run_reject(user, 'comment')
            preprints[2].run_submit(user)
            return preprints

    @pytest.fixture
    def user(self):
        return AuthUserFactory()
