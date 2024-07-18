import pytest
from api.base.settings.defaults import API_BASE
from osf.utils.permissions import WRITE
from osf_tests.factories import (
    PreprintFactory,
    AuthUserFactory,
    ProjectFactory,
    SubjectFactory,
    PreprintProviderFactory,
)

@pytest.mark.django_db
class TestPreprintDetailPermissions:

    @pytest.fixture()
    def user(self):
        return AuthUserFactory()

    @pytest.fixture()
    def admin(self):
        return AuthUserFactory()

    @pytest.fixture()
    def write_contrib(self):
        return AuthUserFactory()

    @pytest.fixture()
    def non_contrib(self):
        return AuthUserFactory()

    @pytest.fixture()
    def public_project(self, admin):
        return ProjectFactory(creator=admin, is_public=True)

    @pytest.fixture()
    def private_project(self, admin):
        return ProjectFactory(creator=admin, is_public=False)

    @pytest.fixture()
    def subject(self):
        return SubjectFactory()

    @pytest.fixture()
    def provider(self):
        return PreprintProviderFactory()

    @pytest.fixture()
    def unpublished_preprint(self, admin, provider, subject, public_project):
        fact = PreprintFactory(
            creator=admin,
            filename='toe_socks_and_sunrises.pdf',
            provider=provider,
            subjects=[[subject._id]],
            is_published=False,
            machine_state='initial')
        assert fact.is_published is False
        return fact

    @pytest.fixture()
    def private_preprint(self, admin, provider, subject, private_project, write_contrib):
        fact = PreprintFactory(
            creator=admin,
            filename='toe_socks_and_sunrises.pdf',
            provider=provider,
            subjects=[[subject._id]],
            is_published=True,
            is_public=False,
            machine_state='accepted')
        fact.add_contributor(write_contrib, permissions=WRITE)
        fact.is_public = False
        fact.save()
        return fact

    @pytest.fixture()
    def published_preprint(self, admin, provider, subject, write_contrib):
        fact = PreprintFactory(
            creator=admin,
            filename='toe_socks_and_sunrises.pdf',
            provider=provider,
            subjects=[[subject._id]],
            is_published=True,
            is_public=True,
            machine_state='accepted')
        fact.add_contributor(write_contrib, permissions=WRITE)
        return fact

    @pytest.fixture()
    def abandoned_private_preprint(self, admin, provider, subject, private_project):
        return PreprintFactory(
            creator=admin,
            filename='toe_socks_and_sunrises.pdf',
            provider=provider,
            subjects=[[subject._id]],
            project=private_project,
            is_published=False,
            is_public=False,
            machine_state='initial')

    @pytest.fixture()
    def abandoned_public_preprint(self, admin, provider, subject, public_project):
        fact = PreprintFactory(
            creator=admin,
            filename='toe_socks_and_sunrises.pdf',
            provider=provider,
            subjects=[[subject._id]],
            project=public_project,
            is_published=False,
            is_public=True,
            machine_state='initial')
        assert fact.is_public is True
        return fact

    @pytest.fixture()
    def abandoned_private_url(self, abandoned_private_preprint):
        return '/{}preprints/{}/'.format(API_BASE, abandoned_private_preprint._id)

    @pytest.fixture()
    def abandoned_public_url(self, abandoned_public_preprint):
        return '/{}preprints/{}/'.format(API_BASE, abandoned_public_preprint._id)

    @pytest.fixture()
    def unpublished_url(self, unpublished_preprint):
        return '/{}preprints/{}/'.format(API_BASE, unpublished_preprint._id)

    @pytest.fixture()
    def private_url(self, private_preprint):
        return '/{}preprints/{}/'.format(API_BASE, private_preprint._id)

    def test_preprint_is_published_detail(self, app, admin, write_contrib, non_contrib, unpublished_preprint, unpublished_url):
        res = app.get(unpublished_url, auth=admin.auth)
        assert res.json['data']['id'] == unpublished_preprint._id

        res = app.get(unpublished_url, auth=write_contrib.auth, expect_errors=True)
        assert res.status_code == 403

        res = app.get(unpublished_url, auth=non_contrib.auth, expect_errors=True)
        assert res.status_code == 403

        res = app.get(unpublished_url, expect_errors=True)
        assert res.status_code == 401

    def test_preprint_is_public_detail(self, app, admin, write_contrib, non_contrib, private_preprint, private_url):
        res = app.get(private_url, auth=admin.auth)
        assert res.json['data']['id'] == private_preprint._id

        res = app.get(private_url, auth=write_contrib.auth)
        assert res.status_code == 200

        res = app.get(private_url, auth=non_contrib.auth, expect_errors=True)
        assert res.status_code == 403

        res = app.get(private_url, expect_errors=True)
        assert res.status_code == 401

    def test_preprint_is_abandoned_detail(self, app, admin, write_contrib, non_contrib, abandoned_private_preprint, abandoned_public_preprint, abandoned_private_url, abandoned_public_url):
        res = app.get(abandoned_private_url, auth=admin.auth)
        assert res.json['data']['id'] == abandoned_private_preprint._id

        res = app.get(abandoned_private_url, auth=write_contrib.auth, expect_errors=True)
        assert res.status_code == 403

        res = app.get(abandoned_private_url, auth=non_contrib.auth, expect_errors=True)
        assert res.status_code == 403

        res = app.get(abandoned_private_url, expect_errors=True)
        assert res.status_code == 401

        res = app.get(abandoned_public_url, auth=admin.auth)
        assert res.json['data']['id'] == abandoned_public_preprint._id

        res = app.get(abandoned_public_url, auth=write_contrib.auth, expect_errors=True)
        assert res.status_code == 403

        res = app.get(abandoned_public_url, auth=non_contrib.auth, expect_errors=True)
        assert res.status_code == 403

        res = app.get(abandoned_public_url, expect_errors=True)
        assert res.status_code == 401

    def test_access_primary_file_on_unpublished_preprint(self, app, user, write_contrib):
        unpublished = PreprintFactory(creator=user, is_public=True, is_published=False)
        preprint_file_id = unpublished.primary_file._id
        url = '/{}files/{}/'.format(API_BASE, preprint_file_id)
        res = app.get(url, auth=user.auth)
        assert res.status_code == 200
        assert unpublished.is_published is False
        res = app.get(url, expect_errors=True)
        assert res.status_code == 401
        unpublished.add_contributor(write_contrib, permissions=WRITE, save=True)
        res = app.get(url, auth=write_contrib.auth, expect_errors=True)
        assert res.status_code == 403
