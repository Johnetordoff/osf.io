from rest_framework import permissions as drf_permissions

from api.base.utils import get_user_auth
from osf.models.action import NodeRequestAction, PreprintRequestAction
from osf.models.mixins import NodeRequestableMixin, PreprintRequestableMixin
from osf.models.node import Node
from osf.models.preprint import Preprint
from osf.utils.workflows import DefaultTriggers
from osf.utils import permissions as osf_permissions


from rest_framework import permissions as drf_permissions
from api.base.utils import get_user_auth
from osf.models.action import NodeRequestAction
from osf.models.mixins import NodeRequestableMixin
from osf.models.node import Node
from osf.utils.workflows import DefaultTriggers
from osf.utils import permissions as osf_permissions


class NodeRequestPermission(drf_permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        auth = get_user_auth(request)
        if not auth.user:
            return False

        # Determine target, node, and trigger based on object type
        target, node, trigger = None, None, request.data.get('trigger', None)

        if isinstance(obj, NodeRequestAction):
            target, node, trigger = self.handle_node_request_action(obj, trigger)
        elif isinstance(obj, NodeRequestableMixin):
            target, node, trigger = self.handle_node_requestable_mixin(request, obj, trigger)
        elif isinstance(obj, Node):
            node, trigger = self.handle_node(obj, request, trigger)
        else:
            raise ValueError(f'Not a request-related model: {obj}')

        if not node.access_requests_enabled:
            return False

        return self.check_permissions(request, auth, target, node, trigger)

    def handle_node_request_action(self, obj, trigger):
        """Handle permission logic for NodeRequestAction."""
        target = obj.target
        node = obj.target.target
        return target, node, trigger

    def handle_node_requestable_mixin(self, request, obj, trigger):
        """Handle permission logic for NodeRequestableMixin."""
        target = obj
        node = obj.target
        if request.method not in drf_permissions.SAFE_METHODS:
            trigger = trigger or DefaultTriggers.SUBMIT.value
        return target, node, trigger

    def handle_node(self, obj, request, trigger):
        """Handle permission logic for Node."""
        if request.method not in drf_permissions.SAFE_METHODS:
            trigger = DefaultTriggers.SUBMIT.value
        return obj, trigger

    def check_permissions(self, request, auth, target, node, trigger):
        """Check if the user has the appropriate permissions."""
        is_requester = target and target.creator == auth.user or trigger == DefaultTriggers.SUBMIT.value
        is_node_admin = node.has_permission(auth.user, osf_permissions.ADMIN)
        has_view_permission = is_requester or is_node_admin

        if request.method in drf_permissions.SAFE_METHODS:
            return has_view_permission

        if not has_view_permission:
            return False

        if trigger in {DefaultTriggers.ACCEPT.value, DefaultTriggers.REJECT.value}:
            return is_node_admin
        if trigger in {DefaultTriggers.EDIT_COMMENT.value, DefaultTriggers.SUBMIT.value}:
            return is_requester and auth.user not in node.contributors
        return False


class PreprintRequestPermission(drf_permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        auth = get_user_auth(request)
        if auth.user is None:
            return False

        target = None
        if isinstance(obj, PreprintRequestAction):
            target = obj.target
            preprint = obj.target.target
            trigger = request.data.get('trigger', None)
        elif isinstance(obj, PreprintRequestableMixin):
            target = obj
            preprint = obj.target
            # Creating a Request is "submitting"
            trigger = request.data.get('trigger', DefaultTriggers.SUBMIT.value if request.method not in drf_permissions.SAFE_METHODS else None)
        elif isinstance(obj, Preprint):
            preprint = obj
            trigger = DefaultTriggers.SUBMIT.value if request.method not in drf_permissions.SAFE_METHODS else None
        else:
            raise ValueError(f'Not a request-related model: {obj}')

        is_requester = target is not None and target.creator == auth.user or trigger == DefaultTriggers.SUBMIT.value
        is_preprint_admin = preprint.has_permission(auth.user, osf_permissions.ADMIN)
        is_moderator = auth.user.has_perm('withdraw_submissions', preprint.provider)
        has_view_permission = is_requester or is_preprint_admin or is_moderator

        if request.method in drf_permissions.SAFE_METHODS:
            # Requesters, moderators, and preprint admins can view actions
            return has_view_permission
        else:
            if not has_view_permission:
                return False

            if trigger in [DefaultTriggers.ACCEPT.value, DefaultTriggers.REJECT.value]:
                # Only moderators can approve or reject requests
                return is_moderator
            if trigger in [DefaultTriggers.EDIT_COMMENT.value, DefaultTriggers.SUBMIT.value]:
                # Requesters may edit their comment or submit their request
                return is_requester
            return False
