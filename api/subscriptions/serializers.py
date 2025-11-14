from rest_framework import serializers as ser
from api.nodes.serializers import RegistrationProviderRelationshipField
from api.collections_providers.fields import CollectionProviderRelationshipField
from api.preprints.serializers import PreprintProviderRelationshipField
from osf.models import NotificationType, NotificationSubscription
from website.util import api_v2_url


from api.base.serializers import JSONAPISerializer, LinksField
from .fields import FrequencyField

class SubscriptionSerializer(JSONAPISerializer):
    filterable_fields = frozenset([
        'id',
        'event_name',
        'frequency',
    ])

    id = ser.CharField(
        read_only=True,
        source='legacy_id',
        help_text='The id of the subscription fixed for backward compatibility',
    )
    event_name = ser.CharField(read_only=True)
    frequency = FrequencyField(
        source='message_frequency',
        required=True,
    )

    class Meta:
        type_ = 'subscription'

    links = LinksField({
        'self': 'get_absolute_url',
    })

    def get_absolute_url(self, obj):
        return obj.absolute_api_v2_url

    def update(self, instance, validated_data):
        freq = validated_data.get('message_frequency')
        if instance.name in (
            NotificationType.Type.PROVIDER_NEW_PENDING_SUBMISSIONS,
            NotificationType.Type.PROVIDER_NEW_PENDING_WITHDRAW_REQUESTS,
        ):
            NotificationSubscription.get_or_create(  # Legacy subscription keeps global settings
                user=instance.user,
                notification_type=NotificationType.Type.REVIEWS_SUBMISSION_STATUS.instance,
                defaults={
                    'message_frequency': freq,
                },
            )
            NotificationSubscription.objects.filter(
                user=instance.user,
                notification_type__in=[
                    NotificationType.Type.REVIEWS_SUBMISSION_STATUS.instance,
                    NotificationType.Type.PROVIDER_NEW_PENDING_SUBMISSIONS.instance,
                ],
            ).update(frequency=freq)
        elif instance.name == NotificationType.Type.USER_FILE_UPDATED:
            NotificationSubscription.objects.filter(
                user=instance.user,
                notification_type__in=[
                    NotificationType.Type.USER_FILE_UPDATED,
                    NotificationType.Type.ADDON_FILE_RENAMED.instance,
                    NotificationType.Type.ADDON_FILE_COPIED.instance,
                    NotificationType.Type.FILE_ADDED.instance,
                    NotificationType.Type.ADDON_FILE_MOVED.instance,
                    NotificationType.Type.FILE_REMOVED.instance,
                    NotificationType.Type.FILE_UPDATED.instance,
                    NotificationType.Type.FOLDER_CREATED.instance,
                ],
            ).update(frequency=freq)
        else:
            if freq is None:
                freq = validated_data.get('frequency')
            instance.message_frequency = freq
            instance.save()
        return instance


class RegistrationSubscriptionSerializer(SubscriptionSerializer):
    provider = RegistrationProviderRelationshipField(
        related_view='providers:registration-providers:registration-provider-detail',
        related_view_kwargs={'provider_id': '<provider._id>'},
        read_only=False,
        required=False,
    )

    def get_absolute_url(self, obj):
        return api_v2_url(f'registration_subscriptions/{obj._id}')

    class Meta:
        type_ = 'registration-subscription'


class CollectionSubscriptionSerializer(SubscriptionSerializer):
    provider = CollectionProviderRelationshipField(
        related_view='providers:collection-providers:collection-provider-detail',
        related_view_kwargs={'provider_id': '<provider._id>'},
        read_only=False,
        required=False,
    )

    def get_absolute_url(self, obj):
        return api_v2_url(f'collection_subscriptions/{obj._id}')

    class Meta:
        type_ = 'collection-subscription'


class PreprintSubscriptionSerializer(SubscriptionSerializer):
    provider = PreprintProviderRelationshipField(
        related_view='providers:preprint-providers:preprint-provider-detail',
        related_view_kwargs={'provider_id': '<provider._id>'},
        read_only=False,
    )

    def get_absolute_url(self, obj):
        return api_v2_url(f'preprints_subscriptions/{obj._id}')

    class Meta:
        type_ = 'preprint-subscription'
