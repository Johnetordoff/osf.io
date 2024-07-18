import pytest
from osf_tests.factories import PreprintFactory, AuthUserFactory
from api.base.settings.defaults import API_BASE

@pytest.fixture()
def user():
    return AuthUserFactory()

@pytest.mark.django_db
class TestPreprintDelete:

    @pytest.fixture()
    def unpublished_preprint(self, user):
        return PreprintFactory(creator=user, is_published=False)

    @pytest.fixture()
    def published_preprint(self, user):
        return PreprintFactory(creator=user)

    @pytest.fixture()
    def url(self, user):
        return '/{}preprints/{{}}/'.format(API_BASE)

    def test_cannot_delete_preprints(self, app, user, url, unpublished_preprint, published_preprint):
        res = app.delete(url.format(unpublished_preprint._id), auth=user.auth, expect_errors=True)
        assert res.status_code == 405
        assert unpublished_preprint.deleted is None

        res = app.delete(url.format(published_preprint._id), auth=user.auth, expect_errors=True)
        assert res.status_code == 405
        assert published_preprint.deleted is None
