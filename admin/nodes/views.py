from __future__ import unicode_literals

import pytz
from datetime import datetime
from framework import status

from django.db.models import F, Case, When, IntegerField
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.views.generic import ListView, View, TemplateView
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import HttpResponse

from website import search
from osf.models import NodeLog
from osf.models.user import OSFUser
from osf.models.node import Node, AbstractNode
from osf.models.registrations import Registration
from osf.models import SpamStatus
from admin.base.utils import change_embargo_date, validate_embargo_date
from admin.base.views import GuidFormView, GuidView
from osf.models.admin_log_entry import (
    update_admin_log,
    NODE_REMOVED,
    NODE_RESTORED,
    CONTRIBUTOR_REMOVED,
    CONFIRM_SPAM,
    CONFIRM_HAM,
    REINDEX_SHARE,
    REINDEX_ELASTIC,
)
from admin.nodes.templatetags.node_extras import reverse_node
from api.share.utils import update_share
from api.caching.tasks import update_storage_usage_cache
from website.settings import STORAGE_LIMIT_PUBLIC, STORAGE_LIMIT_PRIVATE, StorageLimits


class NodeMixin(PermissionRequiredMixin):

    def get_object(self):
        return AbstractNode.objects.filter(
            guids___id=self.kwargs['guid']
        ).annotate(
            guid=F('guids___id'),
            public_cap=Case(
                When(
                    custom_storage_usage_limit_public=None,
                    then=STORAGE_LIMIT_PUBLIC,
                ),
                When(
                    custom_storage_usage_limit_public__gt=0,
                    then=F('custom_storage_usage_limit_public'),
                ),
                output_field=IntegerField()
            ),
            private_cap=Case(
                When(
                    custom_storage_usage_limit_private=None,
                    then=STORAGE_LIMIT_PRIVATE,
                ),
                When(
                    custom_storage_usage_limit_private__gt=0,
                    then=F('custom_storage_usage_limit_private'),
                ),
                output_field=IntegerField()
            )
        ).get()

    def get_success_url(self):
        return reverse_node(self.kwargs['guid'])


class NodeSearchView(PermissionRequiredMixin, GuidFormView):
    """ Allows authorized users to search for a node by it's guid.
    """
    template_name = 'nodes/search.html'
    permission_required = 'osf.view_node'
    raise_exception = True

    @property
    def success_url(self):
        return reverse_node(self.guid)


class NodeRemoveContributorView(NodeMixin, View):
    """ Allows authorized users to remove a contributor from a node.
    """
    permission_required = ('osf.view_node', 'osf.change_node')
    raise_exception = True

    def post(self, request, *args, **kwargs):
        node = self.get_object()
        user = OSFUser.objects.get(id=self.kwargs.get('user_id'))
        if node.remove_contributor(user, None, log=False):
            update_admin_log(
                user_id=self.request.user.id,
                object_id=node.pk,
                object_repr='Contributor',
                message=f'User {user.pk} removed from {node.__class__.__name__.lower()} {node.pk}.',
                action_flag=CONTRIBUTOR_REMOVED
            )
            # Log invisibly on the OSF.
            self.add_contributor_removed_log(node, user)
        return redirect(self.get_success_url())

    def add_contributor_removed_log(self, node, user):
        NodeLog(
            action=NodeLog.CONTRIB_REMOVED,
            user=None,
            params={
                'project': node.parent_id,
                'node': node.pk,
                'contributors': user.pk
            },
            date=timezone.now(),
            should_hide=True,
        ).save()


class NodeDeleteView(NodeMixin, TemplateView):
    """ Allows an authorized user to mark a node as deleted.
    """
    template_name = 'nodes/remove_node.html'
    permission_required = ('osf.view_node', 'osf.delete_node')
    raise_exception = True

    def post(self, request, *args, **kwargs):
        node = self.get_object()
        if node.is_deleted:
            node.is_deleted = False
            node.deleted_date = None
            node.deleted = None
            update_admin_log(
                user_id=self.request.user.id,
                object_id=node.pk,
                object_repr='Node',
                message=f'Node {node.pk} restored.',
                action_flag=NODE_RESTORED
            )
            NodeLog(
                action=NodeLog.NODE_CREATED,
                user=None,
                params={
                    'project': node.parent_id,
                },
                date=timezone.now(),
                should_hide=True,
            ).save()
        elif not node.is_registration:
            node.is_deleted = True
            node.deleted = timezone.now()
            node.deleted_date = node.deleted
            update_admin_log(
                user_id=self.request.user.id,
                object_id=node.pk,
                object_repr='Node',
                message=f'Node {node.pk} removed.',
                action_flag=NODE_REMOVED
            )
            NodeLog(
                action=NodeLog.NODE_REMOVED,
                user=None,
                params={
                    'project': node.parent_id,
                },
                date=timezone.now(),
                should_hide=True,
            ).save()
        node.save()

        return redirect(self.get_success_url())


class NodeView(NodeMixin, GuidView):
    """ Allows authorized users to view node info.
    """
    template_name = 'nodes/node.html'
    permission_required = 'osf.view_node'
    raise_exception = True

    def get_context_data(self, **kwargs):
        return super().get_context_data(**{
            'SPAM_STATUS': SpamStatus,  # Pass spam status in to check against
            'message': kwargs.get('message'),
            'STORAGE_LIMITS': StorageLimits,
            'node': self.get_object(),
        })


class AdminNodeLogView(NodeMixin, ListView):
    """ Allows authorized users to view node logs.
    """
    template_name = 'nodes/node_logs.html'
    paginate_by = 10
    paginate_orphans = 1
    ordering = 'date'
    permission_required = 'osf.view_node'
    raise_exception = True

    def get_queryset(self):
        return self.get_object().logs.order_by('created')

    def get_context_data(self, **kwargs):
        query_set = self.get_queryset()
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(
            query_set, page_size)

        return {
            'logs': query_set,
            'page': page,
        }


class AdminNodeSchemaResponseView(NodeMixin, ListView):
    """ Allows authorized users to view schema response info.
    """
    template_name = 'schema_response/schema_response_list.html'
    paginate_by = 10
    paginate_orphans = 1
    ordering = 'date'
    permission_required = 'osf.view_schema_response'
    raise_exception = True

    def get_queryset(self):
        return self.get_object().schema_responses.all()

    def get_context_data(self, **kwargs):
        return {'schema_responses': self.get_queryset()}


class RegistrationListView(PermissionRequiredMixin, ListView):
    """ Allow authorized users to view the list of registrations of a node.
    """
    template_name = 'nodes/registration_list.html'
    paginate_by = 10
    paginate_orphans = 1
    ordering = 'created'
    permission_required = 'osf.view_registration'
    raise_exception = True

    def get_queryset(self):
        # Django template does not like attributes with underscores for some reason, so we annotate.
        return Registration.objects.all().annotate(guid=F('guids___id')).order_by(self.ordering)

    def get_context_data(self, **kwargs):
        query_set = self.get_queryset()
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(query_set, page_size)
        return {
            'nodes': query_set,
            'page': page,
        }


class StuckRegistrationListView(RegistrationListView):
    """ Allows authorized users to view a list of registrations the have been archiving files by more then 24 hours.
    """

    def get_queryset(self):
        # Django template does not like attributes with underscores for some reason, so we annotate.
        return Registration.find_failed_registrations().annotate(guid=F('guids___id'))


class RegistrationBacklogListView(RegistrationListView):
    """ List view that filters by registrations the haven't been archived at archive.org/
    """

    def get_queryset(self):
        # Django template does not like attributes with underscores for some reason, so we annotate.
        return Registration.find_ia_backlog().annotate(guid=F('guids___id'))


class DoiBacklogListView(RegistrationListView):
    """ Allows authorized users to view a list of registrations that have not yet been assigned a doi.
    """

    def get_queryset(self):
        # Django template does not like attributes with underscores for some reason, so we annotate.
        return Registration.find_doi_backlog().annotate(guid=F('guids___id'))


class RegistrationUpdateEmbargoView(NodeMixin, View):
    """ Allows authorized users to update the embargo of a registration.
    """
    permission_required = ('osf.change_node')
    raise_exception = True

    def post(self, request, *args, **kwargs):
        validation_only = (request.POST.get('validation_only', False) == 'True')
        end_date = request.POST.get('date')
        user = request.user
        registration = self.get_object()

        try:
            end_date = pytz.utc.localize(datetime.strptime(end_date, '%m/%d/%Y'))
        except ValueError:
            return HttpResponse('Please enter a valid date.', status=400)

        try:
            if validation_only:
                validate_embargo_date(registration, user, end_date)
            else:
                change_embargo_date(registration, user, end_date)
        except ValidationError as e:
            return HttpResponse(e, status=409)
        except PermissionDenied as e:
            return HttpResponse(e, status=403)

        return redirect(self.get_success_url())


class NodeSpamList(PermissionRequiredMixin, ListView):
    """ Allows authorized users to view a list of users that have a particular spam status.
    """
    SPAM_STATE = SpamStatus.UNKNOWN

    paginate_by = 25
    paginate_orphans = 1
    ordering = 'created'
    permission_required = 'osf.view_spam'
    raise_exception = True

    def get_queryset(self):
        return Node.objects.filter(
            spam_status=self.SPAM_STATE
        ).order_by(
            self.ordering
        ).annotate(guid=F('guids___id'))

    def get_context_data(self, **kwargs):
        query_set = self.get_queryset()
        page_size = self.get_paginate_by(query_set)
        paginator, page, query_set, is_paginated = self.paginate_queryset(query_set, page_size)
        return {'nodes': query_set, 'page': page}


class NodeFlaggedSpamList(NodeSpamList, View):
    """ Allows authorized users to mark user flagged as spam to be marked as either spam or ham.
    """
    SPAM_STATE = SpamStatus.FLAGGED
    template_name = 'nodes/flagged_spam_list.html'

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm('osf.mark_spam'):
            raise PermissionDenied("You don't have permission to update this user's spam status.")

        data = dict(request.POST)
        action = data.pop('action')[0]
        data.pop('csrfmiddlewaretoken', None)

        if action == 'spam':
            for node_id in list(data):
                node = AbstractNode.objects.get(id=node_id)
                node.confirm_spam()
                update_admin_log(
                    user_id=self.request.user.id,
                    object_id=node_id,
                    object_repr='Node',
                    message=f'Confirmed SPAM: {node_id}',
                    action_flag=CONFIRM_SPAM
                )

                if node.get_identifier_value('doi'):
                    node.request_identifier_update(category='doi')

                node.save()

        if action == 'ham':
            for node_id in list(data):
                node = AbstractNode.objects.get(id=node_id)
                node.confirm_ham(save=True)
                update_admin_log(
                    user_id=self.request.user.id,
                    object_id=node_id,
                    object_repr='User',
                    message=f'Confirmed HAM: {node_id}',
                    action_flag=CONFIRM_HAM
                )

                if node.get_identifier_value('doi'):
                    node.request_identifier_update(category='doi')

                node.save()

        return redirect('nodes:flagged-spam')


class NodeKnownSpamList(NodeSpamList):
    """ Allows authorized users to view a list of users that have a spam status of being spam.
    """

    SPAM_STATE = SpamStatus.SPAM
    template_name = 'nodes/known_spam_list.html'


class NodeKnownHamList(NodeSpamList):
    """ Allows authorized users to view a list of users that have a spam status of being ham (non-spam).
    """
    SPAM_STATE = SpamStatus.HAM
    template_name = 'nodes/known_spam_list.html'


class NodeConfirmSpamView(NodeMixin, View):
    """ Allows authorized users to mark a particular node as spam.
    """
    permission_required = 'osf.mark_spam'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        node = self.get_object()
        node.confirm_spam(save=True)

        if node.get_identifier_value('doi'):
            node.request_identifier_update(category='doi')

        update_admin_log(
            user_id=self.request.user.id,
            object_id=node._id,
            object_repr='Node',
            message=f'Confirmed SPAM: {node._id}',
            action_flag=CONFIRM_SPAM
        )
        return redirect(self.get_success_url())


class NodeConfirmHamView(NodeMixin, View):
    """ Allows authorized users to mark a particular node as ham.
    """
    permission_required = 'osf.mark_spam'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        node = self.get_object()
        node.confirm_ham(save=True)

        if node.get_identifier_value('doi'):
            node.request_identifier_update(category='doi')

        update_admin_log(
            user_id=self.request.user.id,
            object_id=node._id,
            object_repr='Node',
            message=f'Confirmed HAM: {node._id}',
            action_flag=CONFIRM_HAM
        )
        return redirect(self.get_success_url())


class NodeReindexShare(NodeMixin, View):
    permission_required = 'osf.mark_spam'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        node = self.get_object()
        update_share(node)
        update_admin_log(
            user_id=self.request.user.id,
            object_id=node._id,
            object_repr='Node',
            message=f'Node Reindexed (SHARE): {node._id}',
            action_flag=REINDEX_SHARE
        )
        return redirect(self.get_success_url())


class NodeReindexElastic(NodeMixin, View):
    permission_required = 'osf.mark_spam'

    def post(self, request, *args, **kwargs):
        node = self.get_object()
        search.search.update_node(node, bulk=False, async_update=False)

        update_admin_log(
            user_id=self.request.user.id,
            object_id=node._id,
            object_repr='Node',
            message=f'Node Reindexed (Elastic): {node._id}',
            action_flag=REINDEX_ELASTIC
        )
        return redirect(self.get_success_url())


class NodeModifyStorageUsage(NodeMixin, View):
    permission_required = 'osf.change_node'

    def post(self, request, *args, **kwargs):
        node = self.get_object()
        new_private_cap = request.POST.get('private-cap-input')
        new_public_cap = request.POST.get('public-cap-input')

        if float(new_private_cap) != (node.custom_storage_usage_limit_private or STORAGE_LIMIT_PRIVATE):
            node.custom_storage_usage_limit_private = new_private_cap

        if float(new_public_cap) != (node.custom_storage_usage_limit_public or STORAGE_LIMIT_PUBLIC):
            node.custom_storage_usage_limit_public = new_public_cap

        node.save()
        return redirect(self.get_success_url())


class NodeRecalculateStorage(NodeMixin, View):
    permission_required = 'osf.change_node'

    def post(self, request, *args, **kwargs):
        node = self.get_object()
        update_storage_usage_cache(node.id, node._id)
        return redirect(self.get_success_url())


class NodeMakePrivate(NodeMixin, View):
    permission_required = 'osf.change_node'
    template_name = 'nodes/make_private.html'

    def post(self, request, *args, **kwargs):
        node = self.get_object()

        node.is_public = False
        node.keenio_read_key = ''

        # After set permissions callback
        for addon in node.get_addons():
            message = addon.after_set_privacy(node, 'private')
            if message:
                status.push_status_message(message, kind='info', trust=False)

        if node.get_identifier_value('doi'):
            node.request_identifier_update(category='doi')

        node.save()

        return redirect(self.get_success_url())


class RestartStuckRegistrationsView(NodeMixin, TemplateView):
    template_name = 'nodes/restart_registrations_modal.html'
    permission_required = ('osf.view_node', 'osf.change_node')

    def post(self, request, *args, **kwargs):
        # Prevents circular imports that cause admin app to hang at startup
        from osf.management.commands.force_archive import archive, verify
        stuck_reg = self.get_object()
        if verify(stuck_reg):
            try:
                archive(stuck_reg)
                messages.success(request, 'Registration archive processes has restarted')
            except Exception as exc:
                messages.error(request, f'This registration cannot be unstuck due to {exc.__class__.__name__} '
                                        f'if the problem persists get a developer to fix it.')
        else:
            messages.error(request, 'This registration may not technically be stuck,'
                                    ' if the problem persists get a developer to fix it.')

        return redirect(self.get_success_url())


class RemoveStuckRegistrationsView(NodeMixin, TemplateView):
    template_name = 'nodes/remove_registrations_modal.html'
    permission_required = ('osf.view_node', 'osf.change_node')

    def post(self, request, *args, **kwargs):
        stuck_reg = self.get_object()
        if Registration.find_failed_registrations().filter(id=stuck_reg.id).exists():
            stuck_reg.delete_registration_tree(save=True)
            messages.success(request, 'The registration has been deleted')
        else:
            messages.error(request, 'This registration may not technically be stuck,'
                                    ' if the problem persists get a developer to fix it.')

        return redirect(self.get_success_url())
