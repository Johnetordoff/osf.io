import pytest

from osf_tests.factories import (
    SchemaResponsesFactory,
    RegistrationFactory,
    RegistrationSchemaFactory,
    AuthUserFactory,
)
from django.contrib.contenttypes.models import ContentType
from osf.models.schema_responses import SchemaResponses


@pytest.mark.django_db
class TestRegistrationsSchemaResponseList:

    @pytest.fixture()
    def non_contrib(self):
        return AuthUserFactory()

    @pytest.fixture()
    def user(self):
        return AuthUserFactory()

    @pytest.fixture()
    def user_write(self):
        return AuthUserFactory()

    @pytest.fixture()
    def user_admin(self):
        return AuthUserFactory()

    @pytest.fixture()
    def registration(self, schema):
        return RegistrationFactory()

    @pytest.fixture()
    def payload(self, registration):
        return {
            'data':
                {
                    'type': 'registrations',
                    'relationships': {
                        'registration': {
                            'data': {
                                'id': registration._id,
                                'type': 'revisions',
                                'attributes': {
                                    'revision_justification': "We're talkin' about practice..."
                                }
                            }
                        }
                    }
                }
        }

    @pytest.fixture()
    def schema(self):
        return RegistrationSchemaFactory()

    @pytest.fixture()
    def schema_response(self, user, user_write, user_admin, registration, schema):
        registration.add_contributor(user, permissions='read')
        registration.add_contributor(user_write, permissions='write')
        registration.add_contributor(user_admin, permissions='admin')
        content_type = ContentType.objects.get_for_model(registration)
        return SchemaResponsesFactory(
            content_type=content_type,
            object_id=registration.id,
            initiator=registration.creator,
            revision_justification="We ain't even talking about the game.",
            reviews_state='revision_in_progress'
        )

    @pytest.fixture()
    def schema_response2(self, registration, schema):
        content_type = ContentType.objects.get_for_model(registration)
        return SchemaResponsesFactory(content_type=content_type, object_id=registration.id, initiator=registration.creator)

    @pytest.fixture()
    def url(self, registration):
        return f'/v2/registrations/{registration._id}/revisions/'

    def test_registrations_schema_responses_list(self, app, schema_response, schema_response2, user, url):
        resp = app.get(url, auth=user.auth)
        assert resp.status_code == 200
        data = resp.json['data']

        assert len(data) == 2
        assert schema_response2._id == data[0]['id']
        assert schema_response._id == data[1]['id']

    def test_registrations_schema_responses_list_create(self, app, payload, user, url):
        resp = app.post_json_api(url, payload, auth=user.auth)
        assert resp.status_code == 201
        data = resp.json['data']

        assert SchemaResponses.objects.count() == 1
        schema_response = SchemaResponses.objects.last()

        assert data['id'] == schema_response._id
        assert schema_response.revision_justification == "We're talkin' about practice..."
