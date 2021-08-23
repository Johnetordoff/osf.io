from rest_framework import generics, permissions as drf_permissions
from api.base import permissions as base_permissions
from api.base.views import JSONAPIBaseView
from api.nodes.permissions import SchemaResponseViewPermission

from api.schema_responses.serializers import (
    SchemaResponseListSerializer,
    SchemaResponseDetailSerializer,
)
from osf.models import SchemaResponse
from api.base.filters import ListFilterMixin


class SchemaResponseList(JSONAPIBaseView, ListFilterMixin, generics.ListAPIView):
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    serializer_class = SchemaResponseListSerializer
    view_category = 'schema_responses'
    view_name = 'schema-responses-list'

    def get_queryset(self):
        return SchemaResponse.objects.filter()  # TODO: Filter for status


class SchemaResponseDetail(JSONAPIBaseView, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (
        SchemaResponseViewPermission,
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    serializer_class = SchemaResponseDetailSerializer
    view_category = 'schema_responses'
    view_name = 'schema-responses-detail'

    def get_object(self):
        return SchemaResponse.objects.get(_id=self.kwargs['schema_response_id'])

    def perform_destroy(self, instance):
        ## check state
        instance.delete()
