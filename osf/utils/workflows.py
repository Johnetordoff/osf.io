# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from enum import Enum, IntEnum, unique


class ModerationEnum(IntEnum):
    '''A helper Enum superclass that provides easy translation to Int/CharChoices fields.'''

    @classmethod
    def int_field_choices(cls):
        return tuple((member.value, member.readable_value) for member in cls)

    @classmethod
    def char_field_choices(cls):
        return tuple((member.db_name, member.readable_value) for member in cls)

    @classmethod
    def from_db_name(cls, state_db_name):
        return cls[state_db_name.upper()]

    @property
    def readable_value(self):
        return super().name.title().replace('_', '')

    @property
    def db_name(self):
        return self.name.lower()

    @classmethod
    def excluding(cls, *excluded_roles):
        return [role for role in cls if role not in excluded_roles]


class SanctionTypes(ModerationEnum):
    '''A simple descriptor for the type of a sanction class'''

    UNDEFINED = 0
    REGISTRATION_APPROVAL = 1
    EMBARGO = 2
    RETRACTION = 3
    EMBARGO_TERMINATION_APPROVAL = 4
    DRAFT_REGISTRATION_APPROVAL = 5


class SanctionsStates(ModerationEnum):
    '''The moderated state of a Sanction object.'''

    UNDEFINED = 0
    UNAPPROVED = 1
    PENDING_MODERATION = 2
    APPROVED = 3
    REJECTED = 4
    MODERATOR_REJECTED = 5
    COMPLETED = 6  # Embargo only
    IN_PROGRESS = 7  # Revisions only


class CollectionSubmissionStates(ModerationEnum):
    '''The states of a CollectionSubmission object.'''

    IN_PROGRESS = 1
    PENDING = 2
    REJECTED = 3
    ACCEPTED = 4
    REMOVED = 5


class RegistrationModerationStates(ModerationEnum):
    '''The publication state of a Registration object'''
    UNDEFINED = 0
    INITIAL = 1
    REVERTED = 2
    PENDING = 3
    REJECTED = 4
    ACCEPTED = 5
    EMBARGO = 6
    PENDING_EMBARGO_TERMINATION = 7
    PENDING_WITHDRAW_REQUEST = 8
    PENDING_WITHDRAW = 9
    WITHDRAWN = 10

    @classmethod
    def from_sanction(cls, sanction):
        '''Returns a RegistrationModerationState based on sanction's type and state.'''
        # Define every time because it gets interpreted as an enum member in the class body :(
        SANCTION_STATE_MAP = {
            SanctionTypes.REGISTRATION_APPROVAL: {
                SanctionsStates.UNAPPROVED: cls.INITIAL,
                SanctionsStates.PENDING_MODERATION: cls.PENDING,
                SanctionsStates.APPROVED: cls.ACCEPTED,
                SanctionsStates.REJECTED: cls.REVERTED,
                SanctionsStates.MODERATOR_REJECTED: cls.REJECTED,
            },
            SanctionTypes.EMBARGO: {
                SanctionsStates.UNAPPROVED: cls.INITIAL,
                SanctionsStates.PENDING_MODERATION: cls.PENDING,
                SanctionsStates.APPROVED: cls.EMBARGO,
                SanctionsStates.COMPLETED: cls.ACCEPTED,
                SanctionsStates.REJECTED: cls.REVERTED,
                SanctionsStates.MODERATOR_REJECTED: cls.REJECTED,
            },
            SanctionTypes.RETRACTION: {
                SanctionsStates.UNAPPROVED: cls.PENDING_WITHDRAW_REQUEST,
                SanctionsStates.PENDING_MODERATION: cls.PENDING_WITHDRAW,
                SanctionsStates.APPROVED: cls.WITHDRAWN,
                # Rejected retractions are in either ACCEPTED or EMBARGO
                SanctionsStates.REJECTED: cls.UNDEFINED,
                SanctionsStates.MODERATOR_REJECTED: cls.UNDEFINED,
            },
            SanctionTypes.EMBARGO_TERMINATION_APPROVAL: {
                SanctionsStates.UNAPPROVED: cls.PENDING_EMBARGO_TERMINATION,
                SanctionsStates.PENDING_MODERATION: cls.ACCEPTED,  # Not currently reachable
                SanctionsStates.APPROVED: cls.ACCEPTED,
                SanctionsStates.REJECTED: cls.EMBARGO,
                SanctionsStates.MODERATOR_REJECTED: cls.EMBARGO,  # Not currently reachable
            },
        }

        try:
            new_state = SANCTION_STATE_MAP[sanction.SANCTION_TYPE][sanction.approval_stage]
        except KeyError:
            new_state = cls.UNDEFINED

        return new_state


class RegistrationModerationTriggers(ModerationEnum):
    '''The acceptable 'triggers' to describe a moderated action on a Registration.'''

    SUBMIT = 0
    ACCEPT_SUBMISSION = 1
    REJECT_SUBMISSION = 2
    REQUEST_WITHDRAWAL = 3
    ACCEPT_WITHDRAWAL = 4
    REJECT_WITHDRAWAL = 5
    FORCE_WITHDRAW = 6

    @classmethod
    def from_transition(cls, from_state, to_state):
        '''Infer a trigger from a from_state/to_state pair.'''
        moderation_states = RegistrationModerationStates
        transition_to_trigger_mappings = {
            (moderation_states.INITIAL, moderation_states.PENDING): cls.SUBMIT,
            (moderation_states.PENDING, moderation_states.ACCEPTED): cls.ACCEPT_SUBMISSION,
            (moderation_states.PENDING, moderation_states.EMBARGO): cls.ACCEPT_SUBMISSION,
            (moderation_states.PENDING, moderation_states.REJECTED): cls.REJECT_SUBMISSION,
            (moderation_states.PENDING_WITHDRAW_REQUEST,
                moderation_states.PENDING_WITHDRAW): cls.REQUEST_WITHDRAWAL,
            (moderation_states.PENDING_WITHDRAW,
                moderation_states.WITHDRAWN): cls.ACCEPT_WITHDRAWAL,
            (moderation_states.PENDING_WITHDRAW, moderation_states.ACCEPTED): cls.REJECT_WITHDRAWAL,
            (moderation_states.PENDING_WITHDRAW, moderation_states.EMBARGO): cls.REJECT_WITHDRAWAL,
            (moderation_states.ACCEPTED, moderation_states.WITHDRAWN): cls.FORCE_WITHDRAW,
            (moderation_states.EMBARGO, moderation_states.WITHDRAWN): cls.FORCE_WITHDRAW,
        }
        return transition_to_trigger_mappings.get((from_state, to_state))


class SchemaResponseTriggers(ModerationEnum):
    '''The acceptable 'triggers' to use with a SchemaResponseAction'''
    SUBMIT = 0
    APPROVE = 1  # Resource admins "approve" a submission
    ACCEPT = 2  # Moderators "accept" a submission
    ADMIN_REJECT = 3
    MODERATOR_REJECT = 4

    @classmethod
    def from_transition(cls, from_state, to_state):
        transition_to_trigger_mappings = {
            (SanctionsStates.IN_PROGRESS, SanctionsStates.UNAPPROVED): cls.SUBMIT,
            (SanctionsStates.UNAPPROVED, SanctionsStates.UNAPPROVED): cls.APPROVE,
            (SanctionsStates.UNAPPROVED, SanctionsStates.APPROVED): cls.APPROVE,
            (SanctionsStates.UNAPPROVED, SanctionsStates.PENDING_MODERATION): cls.APPROVE,
            (SanctionsStates.PENDING_MODERATION, SanctionsStates.APPROVED): cls.ACCEPT,
            (SanctionsStates.UNAPPROVED, SanctionsStates.IN_PROGRESS): cls.ADMIN_REJECT,
            (SanctionsStates.PENDING_MODERATION, SanctionsStates.IN_PROGRESS): cls.MODERATOR_REJECT,
        }
        return transition_to_trigger_mappings.get((from_state, to_state))


class CollectionSubmissionsTriggers(ModerationEnum):
    '''The acceptable 'triggers' to use with a CollectionSubmissionsAction'''
    SUBMIT = 0
    ACCEPT = 1
    REJECT = 2
    REMOVE = 3
    RESUBMIT = 4
    CANCEL = 5


@unique
class ChoiceEnum(Enum):
    @classmethod
    def choices(cls):
        return tuple((v, str(v).title()) for v in cls.values())

    @classmethod
    def values(cls):
        return tuple(c.value for c in cls)

    @property
    def db_name(self):
        '''Return the value stored in the database for the enum member.

        For parity with ModerationEnum.
        '''
        return self.value


DEFAULT_STATES = [
    ('INITIAL', 'initial'),
    ('PENDING', 'pending'),
    ('ACCEPTED', 'accepted'),
    ('REJECTED', 'rejected'),
]

PREPRINT_STATES = [
    ('INITIAL', 'initial'),
    ('PENDING', 'pending'),
    ('ACCEPTED', 'accepted'),
    ('REJECTED', 'rejected'),
    ('WITHDRAWN', 'withdrawn'),
]

ABSTRACT_PROVIDER_STATES = [
    ('INITIAL', 'initial'),
    ('PENDING', 'pending'),
    ('ACCEPTED', 'accepted'),
    ('REJECTED', 'rejected'),
    ('WITHDRAWN', 'withdrawn'),
]

REGISTRATION_STATES = [
    ('EMBARGO', 'embargo'),
    ('PENDING_EMBARGO_TERMINATION', 'pending_embargo_termination'),
    ('PENDING_WITHDRAW_REQUEST', 'pending_withdraw_request'),
    ('PENDING_WITHDRAW', 'pending_withdraw'),
    ('WITHDRAW', 'withdraw')
]

DEFAULT_TRIGGERS = [
    ('SUBMIT', 'submit'),
    ('ACCEPT', 'accept'),
    ('REJECT', 'reject'),
    ('EDIT_COMMENT', 'edit_comment'),
]

PREPRINT_TRIGGERS = [
    ('SUBMIT', 'submit'),
    ('ACCEPT', 'accept'),
    ('REJECT', 'reject'),
    ('EDIT_COMMENT', 'edit_comment'),
    ('WITHDRAW', 'withdraw')
]


DefaultStates = ChoiceEnum('DefaultStates', DEFAULT_STATES)
PreprintStates = ChoiceEnum('PreprintStates', PREPRINT_STATES)
RegistrationStates = ChoiceEnum('RegistrationStates', REGISTRATION_STATES)
AbstractProviderStates = ChoiceEnum('AbstractProviderStates', ABSTRACT_PROVIDER_STATES)
DefaultTriggers = ChoiceEnum('DefaultTriggers', DEFAULT_TRIGGERS)
PreprintTriggers = ChoiceEnum('PreprintTriggers', PREPRINT_TRIGGERS)

CHRONOS_STATUS_STATES = [
    ('DRAFT', 1),
    ('SUBMITTED', 2),
    ('ACCEPTED', 3),
    ('PUBLISHED', 4),
    ('CANCELLED', 5),
]

ChronosSubmissionStatus = ChoiceEnum('ChronosSubmissionStatus', CHRONOS_STATUS_STATES)


DEFAULT_TRANSITIONS = [
    {
        'trigger': DefaultTriggers.SUBMIT.value,
        'source': [DefaultStates.INITIAL.value],
        'dest': DefaultStates.PENDING.value,
        'before': ['validate_changes'],
        'after': ['save_action', 'update_last_transitioned', 'save_changes', 'notify_submit'],
    },
    {
        'trigger': DefaultTriggers.SUBMIT.value,
        'source': [DefaultStates.PENDING.value, DefaultStates.REJECTED.value],
        'conditions': 'resubmission_allowed',
        'dest': DefaultStates.PENDING.value,
        'after': ['save_action', 'update_last_transitioned', 'save_changes', 'notify_resubmit'],
    },
    {
        'trigger': DefaultTriggers.ACCEPT.value,
        'source': [DefaultStates.PENDING.value, DefaultStates.REJECTED.value],
        'dest': DefaultStates.ACCEPTED.value,
        'after': ['save_action', 'update_last_transitioned', 'save_changes', 'notify_accept_reject'],
    },
    {
        'trigger': DefaultTriggers.REJECT.value,
        'source': [DefaultStates.PENDING.value, DefaultStates.ACCEPTED.value],
        'dest': DefaultStates.REJECTED.value,
        'after': ['save_action', 'update_last_transitioned', 'save_changes', 'notify_accept_reject'],
    },
    {
        'trigger': DefaultTriggers.EDIT_COMMENT.value,
        'source': [DefaultStates.PENDING.value, DefaultStates.REJECTED.value, DefaultStates.ACCEPTED.value],
        'dest': '=',
        'after': ['save_action', 'save_changes', 'notify_edit_comment'],
    },
]

PREPRINT_TRANSITIONS = [
    {
        'trigger': PreprintTriggers.SUBMIT.value,
        'source': [PreprintStates.INITIAL.value],
        'dest': PreprintStates.PENDING.value,
        'before': ['validate_changes'],
        'after': ['save_action', 'update_last_transitioned', 'save_changes', 'notify_submit'],
    },
    {
        'trigger': PreprintTriggers.SUBMIT.value,
        'source': [PreprintStates.PENDING.value, PreprintStates.REJECTED.value],
        'conditions': 'resubmission_allowed',
        'dest': PreprintStates.PENDING.value,
        'after': ['save_action', 'update_last_transitioned', 'save_changes', 'notify_resubmit'],
    },
    {
        'trigger': PreprintTriggers.ACCEPT.value,
        'source': [PreprintStates.PENDING.value, PreprintStates.REJECTED.value],
        'dest': PreprintStates.ACCEPTED.value,
        'after': ['save_action', 'update_last_transitioned', 'save_changes', 'notify_accept_reject'],
    },
    {
        'trigger': PreprintTriggers.REJECT.value,
        'source': [PreprintStates.PENDING.value, PreprintStates.ACCEPTED.value],
        'dest': PreprintStates.REJECTED.value,
        'after': ['save_action', 'update_last_transitioned', 'save_changes', 'notify_accept_reject'],
    },
    {
        'trigger': PreprintTriggers.EDIT_COMMENT.value,
        'source': [PreprintStates.PENDING.value, PreprintStates.REJECTED.value, PreprintStates.ACCEPTED.value],
        'dest': '=',
        'after': ['save_action', 'save_changes', 'notify_edit_comment'],
    },
    {
        'trigger': PreprintTriggers.WITHDRAW.value,
        'source': [PreprintStates.PENDING.value, PreprintStates.ACCEPTED.value],
        'dest': PreprintStates.WITHDRAWN.value,
        'after': ['save_action', 'update_last_transitioned', 'perform_withdraw', 'save_changes', 'notify_withdraw']
    }
]

SANCTION_TRANSITIONS = [
    {
        # Submit an approvable resource
        'trigger': 'submit',
        'source': [SanctionsStates.IN_PROGRESS],
        'dest': SanctionsStates.UNAPPROVED,
        'before': ['_validate_trigger'],
        'after': ['_on_submit'],
    },
    {
        # A single admin approves an approvable resource
        'trigger': 'approve',  # Approval from an individual admin
        'source': [SanctionsStates.UNAPPROVED],
        'dest': None,
        'before': ['_validate_trigger'],
        'after': ['_on_approve'],
    },
    {
        # Allow delayed admin approvals as a noop in non-rejected states
        'trigger': 'approve',
        'source': [
            SanctionsStates.PENDING_MODERATION,
            SanctionsStates.APPROVED,
            SanctionsStates.COMPLETED
        ],
        'dest': None,
    },
    {
        # A moderated approvable resource has satisfied its Admin approval
        # requirements and is submitted for moderation.
        'trigger': 'accept',
        'source': [SanctionsStates.UNAPPROVED],
        'dest': SanctionsStates.PENDING_MODERATION,
        'conditions': ['is_moderated'],
        'before': ['_validate_trigger'],
        'after': [],  # send moderator emails here?
    },
    {
        # An un moderated approvable resource has satisfied its Admin approval requirements
        # or a moderated sanction receives moderator approval and takes effect
        'trigger': 'accept',
        'source': [SanctionsStates.UNAPPROVED, SanctionsStates.PENDING_MODERATION],
        'dest': SanctionsStates.APPROVED,
        'before': ['_validate_trigger'],
        'after': ['_on_complete'],
    },
    {
        # Allow delayed accept triggers as a noop in completed states
        'trigger': 'accept',
        'source': [SanctionsStates.APPROVED, SanctionsStates.COMPLETED],
        'dest': None,
    },
    {
        # A revisable, approvable resource is rejected by an admin or moderator
        'trigger': 'reject',
        'source': [SanctionsStates.UNAPPROVED, SanctionsStates.PENDING_MODERATION],
        'dest': SanctionsStates.IN_PROGRESS,
        'conditions': ['revisable'],
        'before': ['_validate_trigger'],
        'after': ['_on_reject'],
    },
    {
        # An unrevisable, approvable resource is rejected by an admin
        'trigger': 'reject',
        'source': [SanctionsStates.UNAPPROVED],
        'dest': SanctionsStates.REJECTED,
        'before': ['_validate_trigger'],
        'after': ['_on_reject'],
    },
    {
        # An unrevisable, approvable entity is rejected by a moderator
        'trigger': 'reject',
        'source': [SanctionsStates.PENDING_MODERATION],
        'dest': SanctionsStates.MODERATOR_REJECTED,
        'before': ['_validate_trigger'],
        'after': ['_on_reject'],
    },
    {
        # Allow delayed reject triggers as a noop in rejected states
        'trigger': 'reject',
        'source': [SanctionsStates.REJECTED, SanctionsStates.MODERATOR_REJECTED],
        'dest': None,
    },
]


COLLECTION_SUBMISSION_TRANSITIONS = [
    {
        'trigger': 'submit',
        'source': [CollectionSubmissionStates.IN_PROGRESS],
        'dest': CollectionSubmissionStates.ACCEPTED,
        'before': [],
        'after': ['_notify_accepted'],
        'unless': ['is_moderated', 'is_hybrid_moderated'],
    },
    {
        'trigger': 'submit',
        'source': [CollectionSubmissionStates.IN_PROGRESS],
        'dest': CollectionSubmissionStates.PENDING,
        'before': [],
        'after': ['_notify_contributors_pending', '_notify_moderators_pending'],
        'conditions': ['is_moderated'],
    },
    {
        'trigger': 'submit',
        'source': [CollectionSubmissionStates.IN_PROGRESS],
        'dest': CollectionSubmissionStates.ACCEPTED,
        'before': [],
        'after': ['_notify_contributors_pending', '_notify_moderators_pending'],
        'conditions': ['is_hybrid_moderated', 'is_submitted_by_moderator_contributor'],
    },
    {
        'trigger': 'submit',
        'source': [CollectionSubmissionStates.IN_PROGRESS],
        'dest': CollectionSubmissionStates.PENDING,
        'before': [],
        'conditions': ['is_hybrid_moderated'],
        'after': ['_notify_contributors_pending', '_notify_moderators_pending'],
        'unless': ['is_submitted_by_moderator_contributor'],
    },
    {
        'trigger': 'accept',
        'source': [CollectionSubmissionStates.PENDING],
        'dest': CollectionSubmissionStates.ACCEPTED,
        'before': ['_validate_accept'],
        'after': ['_notify_accepted', '_make_public'],
        'conditions': ['is_moderated'],
    },
    {
        'trigger': 'accept',
        'source': [CollectionSubmissionStates.PENDING],
        'dest': CollectionSubmissionStates.ACCEPTED,
        'before': ['_validate_accept'],
        'after': ['_notify_accepted', '_make_public'],
        'conditions': ['is_hybrid_moderated'],
    },
    {
        'trigger': 'reject',
        'source': [CollectionSubmissionStates.PENDING],
        'dest': CollectionSubmissionStates.REJECTED,
        'before': ['_validate_reject'],
        'after': ['_notify_moderated_rejected'],
        'conditions': ['is_moderated'],
    },
    {
        'trigger': 'reject',
        'source': [CollectionSubmissionStates.PENDING],
        'dest': CollectionSubmissionStates.REJECTED,
        'before': ['_validate_reject'],
        'after': ['_notify_moderated_rejected'],
        'conditions': ['is_hybrid_moderated'],
    },
    {
        'trigger': 'remove',
        'source': [CollectionSubmissionStates.ACCEPTED],
        'dest': CollectionSubmissionStates.REMOVED,
        'before': ['_validate_remove'],
        'after': ['_remove_from_search', '_notify_removed'],
        'unless': ['is_hybrid_moderated', 'is_moderated'],
    },
    {
        'trigger': 'remove',
        'source': [CollectionSubmissionStates.ACCEPTED],
        'dest': CollectionSubmissionStates.REMOVED,
        'before': ['_validate_remove'],
        'after': ['_remove_from_search', '_notify_removed'],
        'conditions': ['is_hybrid_moderated'],
    },
    {
        'trigger': 'remove',
        'source': [CollectionSubmissionStates.ACCEPTED],
        'dest': CollectionSubmissionStates.REMOVED,
        'before': ['_validate_remove'],
        'after': ['_remove_from_search', '_notify_removed'],
        'conditions': ['is_moderated'],
    },
    {
        'trigger': 'resubmit',
        'source': [CollectionSubmissionStates.REJECTED, CollectionSubmissionStates.REMOVED],
        'dest': CollectionSubmissionStates.ACCEPTED,
        'before': ['_validate_resubmit'],
        'after': ['_make_public', '_notify_accepted'],
        'unless': ['is_moderated', 'is_hybrid_moderated'],
    },
    {
        'trigger': 'resubmit',
        'source': [CollectionSubmissionStates.REJECTED, CollectionSubmissionStates.REMOVED],
        'dest': CollectionSubmissionStates.PENDING,
        'before': ['_validate_resubmit'],
        'after': ['_make_public', '_notify_contributors_pending', '_notify_moderators_pending'],
        'conditions': ['is_moderated'],
    },
    {
        'trigger': 'resubmit',
        'source': [CollectionSubmissionStates.REJECTED, CollectionSubmissionStates.REMOVED],
        'dest': CollectionSubmissionStates.ACCEPTED,
        'before': [],
        'after': ['_make_public', '_notify_accepted'],
        'conditions': ['is_hybrid_moderated', 'is_submitted_by_moderator_contributor'],
    },
    {
        'trigger': 'resubmit',
        'source': [CollectionSubmissionStates.REJECTED, CollectionSubmissionStates.REMOVED],
        'dest': CollectionSubmissionStates.PENDING,
        'before': ['_validate_resubmit'],
        'after': ['_make_public', '_notify_contributors_pending', '_notify_moderators_pending'],
        'conditions': ['is_hybrid_moderated'],
        'unless': ['is_submitted_by_moderator_contributor']
    },
    {
        'trigger': 'cancel',
        'source': [CollectionSubmissionStates.PENDING],
        'dest': CollectionSubmissionStates.IN_PROGRESS,
        'before': ['_validate_cancel'],
        'after': ['_notify_cancel'],
        'conditions': [],
        'unless': []
    },
]

@unique
class RequestTypes(ChoiceEnum):
    ACCESS = 'access'
    WITHDRAWAL = 'withdrawal'
