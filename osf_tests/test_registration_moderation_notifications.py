import pytest
from django.contrib.contenttypes.models import ContentType

from osf.models import Notification, NotificationType, EmailTask
from notifications.tasks import (
    send_user_email_task,
    send_moderator_email_task,
    send_users_digest_email,
    send_moderators_digest_email,
    get_users_emails,
    get_moderators_emails,
)
from osf_tests.factories import (
    AuthUserFactory,
    RegistrationProviderFactory,
    RegistrationFactory,
)
from tests.utils import capture_notifications


def add_notification_subscription(
    user,
    notification_type,
    frequency,
    subscribed_object=None,
):
    """
    Create a NotificationSubscription for a user.

    `notification_type` may be:
        - a NotificationType instance
        - a NotificationType.Type enum value
        - a raw name string
    """
    from osf.models import NotificationSubscription

    if isinstance(notification_type, NotificationType):
        nt = notification_type
    else:
        # enum or name string
        nt = NotificationType.objects.get(name=notification_type)

    kwargs = {
        'user': user,
        'notification_type': nt,
        'message_frequency': frequency,
    }

    if subscribed_object is not None:
        kwargs['object_id'] = subscribed_object.id
        kwargs['content_type'] = ContentType.objects.get_for_model(subscribed_object)

    return NotificationSubscription.objects.create(**kwargs)


@pytest.mark.django_db
class TestNotificationDigestTasks:

    def test_send_user_email_task_success(self):
        user = AuthUserFactory()
        notification_type = NotificationType.objects.get(
            name=NotificationType.Type.USER_FILE_UPDATED
        )
        add_notification_subscription(
            user,
            NotificationType.objects.get(name=NotificationType.Type.FILE_UPDATED),
            'daily',
        )
        subscription_type = add_notification_subscription(
            user,
            notification_type,
            'daily',
            subscribed_object=user
        )

        subscription_type.emits(
            event_context={
                'source_path': '/',
                'source_node_title': 'test title',
                'source_addon': 'test addon',
                'destination_addon': 'what?',
                'logo': 'test logo',
                'action': 'test action',
                'osf_logo': 'test logo',
                'osf_logo_list': 'osf_logo_list',
                'destination_node_parent_node_title': 'test parent node title',
                'destination_node_title': 'test node title',
            },
        )
        user.save()
        notification = Notification.objects.get()
        notification_ids = [notification.id]
        with capture_notifications() as notifications:
            send_user_email_task.apply(args=(user._id, notification_ids)).get()
        assert len(notifications['emits']) == 1
        assert notifications['emits'][0]['type'] == NotificationType.Type.USER_DIGEST
        assert notifications['emits'][0]['kwargs']['user'] == user
        email_task = EmailTask.objects.get(user_id=user.id)
        assert email_task.status == 'SUCCESS'
        notification.refresh_from_db()
        assert notification.sent

    def test_send_user_email_task_user_not_found(self):
        non_existent_user_id = 'fakeuserid'
        notification_ids = []
        send_user_email_task.apply(args=(non_existent_user_id, notification_ids)).get()
        assert EmailTask.objects.all().exists()
        email_task = EmailTask.objects.all().get()
        assert email_task.status == 'NO_USER_FOUND'
        assert email_task.error_message == 'User not found or disabled'

    def test_send_user_email_task_user_disabled(self):
        user = AuthUserFactory()
        user.deactivate_account()
        user.save()

        # Any subscription is fine; we just need one
        subscription = add_notification_subscription(
            user,
            NotificationType.Type.USER_FILE_UPDATED,
            'daily',
            subscribed_object=user,
        )
        notification = Notification.objects.create(
            subscription=subscription,
            sent=None,
            event_context={},
        )
        notification_ids = [notification.id]
        send_user_email_task.apply(args=(user._id, notification_ids)).get()
        email_task = EmailTask.objects.filter(user_id=user.id).first()
        assert email_task.status == 'USER_DISABLED'
        assert email_task.error_message == 'User not found or disabled'

    def test_send_user_email_task_no_notifications(self):
        user = AuthUserFactory()
        notification_ids = []
        send_user_email_task.apply(args=(user._id, notification_ids)).get()
        email_task = EmailTask.objects.filter(user_id=user.id).first()
        assert email_task.status == 'SUCCESS'

    def test_send_moderator_email_task_registration_provider_admin(self):
        user = AuthUserFactory(fullname='Admin User')
        reg_provider = RegistrationProviderFactory(_id='abc123')
        reg = RegistrationFactory(provider=reg_provider)
        reg_provider.add_to_group(user, 'moderator')
        reg_provider.add_to_group(user, 'admin')

        add_notification_subscription(
            user,
            NotificationType.Type.PROVIDER_NEW_PENDING_SUBMISSIONS.instance,
            'daily',
            subscribed_object=reg,
        ).emit(
            event_context={
                'profile_image_url': 'http://example.com/profile.png',
                'is_request_email': False,
                'requester_contributor_names': ['<NAME>'],
                'reviews_submission_url': 'http://example.com/reviews_submission.png',
                'message': 'test message',
                'requester_fullname': '<NAME>',
                'localized_timestamp': 'test timestamp',
            },
        )
        notification = Notification.objects.get()
        notification_ids = [notification.id]
        with capture_notifications() as notifications:
            send_moderator_email_task.apply(
                args=(user._id, notification_ids)
            ).get()
        assert len(notifications['emits']) == 1
        assert (
            notifications['emits'][0]['type']
            == NotificationType.Type.DIGEST_REVIEWS_MODERATORS
        )
        assert notifications['emits'][0]['kwargs']['user'] == user

        email_task = EmailTask.objects.filter(user_id=user.id).first()
        assert email_task.status == 'SUCCESS'
        notification.refresh_from_db()
        assert notification.sent

    def test_send_moderator_email_task_no_notifications(self):
        user = AuthUserFactory(fullname='Admin User')
        provider = RegistrationProviderFactory()
        reg = RegistrationFactory(provider=provider)

        notification_ids = []
        notification_type = NotificationType.objects.get(
            name=NotificationType.Type.PROVIDER_NEW_PENDING_SUBMISSIONS
        )
        add_notification_subscription(
            user,
            notification_type,
            'daily',
            subscribed_object=reg,
        )

        send_moderator_email_task.apply(args=(user._id, notification_ids)).get()
        email_task = EmailTask.objects.filter(user_id=user.id).first()
        assert email_task.status == 'SUCCESS'

    def test_send_moderator_email_task_user_not_found(self):
        send_moderator_email_task.apply(args=('nouser', [])).get()
        email_task = EmailTask.objects.all()
        assert email_task.exists()
        assert email_task.first().status == 'NO_USER_FOUND'

    def test_get_users_emails(self):
        user = AuthUserFactory()
        notification_type = NotificationType.objects.get(
            name=NotificationType.Type.USER_DIGEST
        )
        notification1 = Notification.objects.create(
            subscription=add_notification_subscription(
                user,
                notification_type,
                'daily',
                subscribed_object=user,
            ),
            sent=None,
            event_context={},
        )
        res = list(get_users_emails('daily'))
        assert len(res) == 1
        user_info = res[0]
        assert user_info['user_id'] == user._id
        assert any(msg['notification_id'] == notification1.id for msg in user_info['info'])

    def test_get_moderators_emails(self):
        user = AuthUserFactory()
        provider = RegistrationProviderFactory()
        reg = RegistrationFactory(provider=provider)
        notification_type = NotificationType.objects.get(
            name=NotificationType.Type.PROVIDER_NEW_PENDING_SUBMISSIONS
        )
        subscription = add_notification_subscription(
            user,
            notification_type,
            'daily',
            subscribed_object=reg,
        )
        Notification.objects.create(
            subscription=subscription,
            event_context={},
            sent=None,
        )
        provider.add_to_group(user, 'moderator')

        res = list(get_moderators_emails('daily'))
        assert len(res) >= 1
        entry = [
            x
            for x in res
            if x['user_id'] == user._id
            and subscription.subscribed_object.id == reg.id
        ]
        assert entry, 'Expected moderator digest group'

    def test_send_users_digest_email_end_to_end(self):
        user = AuthUserFactory()
        notification_type = NotificationType.objects.get(
            name=NotificationType.Type.USER_FILE_UPDATED
        )
        add_notification_subscription(
            user,
            NotificationType.objects.get(name=NotificationType.Type.FILE_UPDATED),
            'daily',
        )
        subscription_type = add_notification_subscription(
            user,
            notification_type,
            'daily',
            subscribed_object=user,
        )

        Notification.objects.create(
            subscription=subscription_type,
            event_context={
                'source_path': '/',
                'requester_fullname': '<NAME>',
                'source_node_title': 'test title',
                'source_addon': 'test addon',
                'destination_addon': 'what?',
                'logo': 'test logo',
                'requester_contributor_names': ['<NAME>'],
                'action': 'test action',
                'osf_logo': 'test logo',
                'osf_logo_list': 'osf_logo_list',
                'profile_image_url': 'http://example.com/profile.png',
                'destination_node_parent_node_title': 'test parent node title',
                'destination_node_title': 'test node title',
                'nessage': 'test message',
                'localized_timestamp': 'test timestamp',
            },
        )
        user.save()
        with capture_notifications() as notifications:
            # call task synchronously for tests
            send_users_digest_email.apply(kwargs={'dry_run': False}).get()
        assert len(notifications['emits']) == 1
        assert notifications['emits'][0]['type'] == NotificationType.Type.USER_DIGEST
        email_task = EmailTask.objects.get(user_id=user.id)
        assert email_task.status == 'SUCCESS'

    def test_send_moderators_digest_email_end_to_end(self):
        user = AuthUserFactory()
        provider = RegistrationProviderFactory()
        provider.add_to_group(user, 'moderator')
        reg = RegistrationFactory(provider=provider)

        add_notification_subscription(
            user,
            NotificationType.Type.PROVIDER_NEW_PENDING_SUBMISSIONS.instance,
            'daily',
            subscribed_object=reg,
        ).emit(
            event_context={
                'submitter_fullname': 'submitter_fullname',
                'requester_fullname': 'requester_fullname',
                'requester_contributor_names': 'requester_contributor_names',
                'localized_timestamp': '2024-01-01T00:00:00Z',
                'message': 'submitted title.',
                'reviews_submission_url': 'reviews_submission_url',
                'is_request_email': False,
                'is_initiator': False,
                'profile_image_url': 'profile_image_url',
            },
        )
        with capture_notifications() as notifications:
            send_moderators_digest_email.apply(kwargs={'dry_run': False}).get()
        assert len(notifications['emits']) == 1
        assert (
            notifications['emits'][0]['type']
            == NotificationType.Type.DIGEST_REVIEWS_MODERATORS
        )
        email_task = EmailTask.objects.filter(user_id=user.id).first()
        assert email_task.status == 'SUCCESS'

    def test_send_users_digest_email_batches_multiple_notifications(self):
        """
        Regression: multiple notifications for same user/frequency
        MUST result in exactly one USER_DIGEST emit.
        """
        user = AuthUserFactory()
        inner_sub = add_notification_subscription(
            user,
            NotificationType.Type.FILE_UPDATED.instance,
            'daily',
            subscribed_object=user,
        )
        add_notification_subscription(
            user,
            NotificationType.Type.USER_FILE_UPDATED.instance,
            'daily',
            subscribed_object=user,
        )

        for i in range(5):
            inner_sub.emit(
                event_context={
                    'profile_image_url': 'http://example.com/profile.png',
                    'localized_timestamp': 'time',
                    'message': 'test message',
                    'url': 'http://example.com',
                    'user_fullname': '<NAME>',
                },
            )

        user.save()
        with capture_notifications() as notifications:
            send_users_digest_email.apply(kwargs={'dry_run': False}).get()

        assert len(notifications['emits']) == 1
        emit = notifications['emits'][0]
        assert emit['type'] == NotificationType.Type.USER_DIGEST
        # Optional: make sure all 5 notifications were in the digest payload
        event_context = emit['kwargs'].get('event_context') or {}
        notifications_ctx = event_context.get('notifications') or []
        assert len(notifications_ctx) == 5

    def test_send_moderators_digest_email_batches_multiple_notifications(self):
        """
        Regression: multiple notifications for same moderator+provider
        MUST result in exactly one DIGEST_REVIEWS_MODERATORS emit.
        """
        user = AuthUserFactory()
        provider = RegistrationProviderFactory()
        reg = RegistrationFactory(provider=provider)
        notification_type = NotificationType.objects.get(
            name=NotificationType.Type.PROVIDER_NEW_PENDING_SUBMISSIONS
        )
        provider.add_to_group(user, 'moderator')

        subscription = add_notification_subscription(
            user,
            notification_type,
            'daily',
            subscribed_object=reg,
        )

        for i in range(4):
            subscription.emit(
                event_context={
                    'submitter_fullname': 'submitter_fullname',
                    'requester_fullname': 'requester_fullname',
                    'requester_contributor_names': 'requester_contributor_names',
                    'localized_timestamp': '2024-01-01T00:00:00Z',
                    'message': 'submitted title.',
                    'reviews_submission_url': 'reviews_submission_url',
                    'is_request_email': False,
                    'is_initiator': False,
                    'profile_image_url': 'profile_image_url',
                },
            )

        with capture_notifications() as notifications:
            send_moderators_digest_email.apply(kwargs={'dry_run': False}).get()

        assert len(notifications['emits']) == 1
        emit = notifications['emits'][0]
        assert (
            emit['type'] == NotificationType.Type.DIGEST_REVIEWS_MODERATORS
        )
        event_context = emit['kwargs'].get('event_context') or {}
        notifications_ctx = event_context.get('notifications') or []
        assert len(notifications_ctx) == 4
