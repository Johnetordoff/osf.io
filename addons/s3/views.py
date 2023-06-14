from rest_framework import status as http_status

import boto3
from boto3 import exceptions
from botocore.exceptions import NoCredentialsError, ClientError
from django.core.exceptions import ValidationError
from flask import request

from framework.exceptions import HTTPError
from framework.auth.decorators import must_be_logged_in

from addons.base import generic_views
from addons.s3 import utils
from addons.s3.serializer import S3Serializer
from osf.models import ExternalAccount
from osf.utils.permissions import WRITE
from website.project.decorators import (
    must_have_addon, must_have_permission,
    must_be_addon_authorizer,
)

SHORT_NAME = 's3'
FULL_NAME = 'Amazon S3'

s3_account_list = generic_views.account_list(
    SHORT_NAME,
    S3Serializer
)

s3_import_auth = generic_views.import_auth(
    SHORT_NAME,
    S3Serializer
)

s3_deauthorize_node = generic_views.deauthorize_node(
    SHORT_NAME
)

s3_get_config = generic_views.get_config(
    SHORT_NAME,
    S3Serializer
)

def _set_folder(node_addon, folder, auth):
    folder_id = folder['id']
    node_addon.set_folder(folder_id, auth=auth)
    node_addon.save()

s3_set_config = generic_views.set_config(
    SHORT_NAME,
    FULL_NAME,
    S3Serializer,
    _set_folder
)

@must_have_addon(SHORT_NAME, 'node')
@must_be_addon_authorizer(SHORT_NAME)
def s3_folder_list(node_addon, **kwargs):
    """ Returns all the subsequent folders under the folder id passed.
    """
    return node_addon.get_folders()

@must_be_logged_in
def s3_add_user_account(auth, **kwargs):
    """Verifies new external account credentials and adds to user's list"""
    try:
        access_key = request.json['access_key']
        secret_key = request.json['secret_key']
    except KeyError:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST)

    if not (access_key and secret_key):
        return {
            'message': 'All the fields above are required.'
        }, http_status.HTTP_400_BAD_REQUEST

    try:
        user_info = utils.get_user_info(access_key, secret_key)
    except NoCredentialsError:
        return {
            'message': 'Invalid AWS credentials.'
        }, http_status.HTTP_400_BAD_REQUEST

    if not user_info:
        return {
            'message': ('Unable to access account.\n'
                'Check to make sure that the above credentials are valid, '
                'and that they have permission to list buckets.')
        }, http_status.HTTP_400_BAD_REQUEST

    if not utils.can_list(access_key, secret_key):
        return {
            'message': ('Unable to list buckets.\n'
                'Listing buckets is required permission that can be changed via IAM')
        }, http_status.HTTP_400_BAD_REQUEST

    try:
        account = ExternalAccount(
            provider=SHORT_NAME,
            provider_name=FULL_NAME,
            oauth_key=access_key,
            oauth_secret=secret_key,
            provider_id=user_info['id'],
            display_name=user_info['display_name'],
        )
        account.save()
    except ValidationError:
        # ... or get the old one
        account = ExternalAccount.objects.get(
            provider=SHORT_NAME,
            provider_id=user_info['id']
        )
        if account.oauth_key != access_key or account.oauth_secret != secret_key:
            account.oauth_key = access_key
            account.oauth_secret = secret_key
            account.save()
    assert account is not None

    if not auth.user.external_accounts.filter(id=account.id).exists():
        auth.user.external_accounts.add(account)

    # Ensure S3 is enabled.
    auth.user.get_or_add_addon('s3', auth=auth)
    auth.user.save()

    return {}


@must_be_addon_authorizer(SHORT_NAME)
@must_have_addon('s3', 'node')
@must_have_permission(WRITE)
def create_bucket(auth, node_addon, **kwargs):
    bucket_name = request.json.get('bucket_name', '')
    bucket_location = request.json.get('bucket_location', '')
    access_key = node_addon.external_account.oauth_key
    secret_key = node_addon.external_account.oauth_secret
    if not utils.validate_bucket_name(bucket_name):
        return {
            'message': 'That bucket name is not valid.',
            'title': 'Invalid bucket name',
        }, http_status.HTTP_400_BAD_REQUEST
    # Get location and verify it is valid
    if not utils.validate_bucket_location(access_key=access_key, secret_key=secret_key, location=bucket_location):
        return {
            'message': 'That bucket location is not valid.',
            'title': 'Invalid bucket location',
        }, http_status.HTTP_400_BAD_REQUEST
    try:
        utils.create_bucket(node_addon, bucket_name, bucket_location)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            return {
                'message': 'Access denied to create the bucket.',
                'title': 'Access Denied',
            }, http_status.HTTP_400_BAD_REQUEST
        elif error_code == 'BucketAlreadyOwnedByYou':
            return {
                'message': 'You already own a bucket with that name.',
                'title': 'Bucket Already Owned',
            }, http_status.HTTP_400_BAD_REQUEST
        elif error_code == 'BucketAlreadyExists':
            return {
                'message': 'There\'s already a bucket with that name.',
                'title': 'Bucket Already Owned',
            }, http_status.HTTP_400_BAD_REQUEST
        elif error_code == 'InvalidLocationConstraint':
            print(bucket_location)
            print(bucket_location)
            if bucket_location == 'us-east-1':  # they are ahead of the new default value
                try:
                    utils.create_bucket(node_addon, bucket_name, None)
                    return {}
                except:
                    pass

            return {
                'message': 'The location you selected is unavailable for you credentials.',
                'title': 'Invalid Location Constraint',
            }, http_status.HTTP_400_BAD_REQUEST
        else:
            return {
                'message': 'An error occurred while creating the bucket.',
                'title': 'Error Creating Bucket',
            }, http_status.HTTP_400_BAD_REQUEST
    except exceptions.Boto3Error as e:  # Base error class for all boto3 exceptions
        return {
            'message': e.message,
            'title': 'Problem connecting to S3',
        }, http_status.HTTP_400_BAD_REQUEST
    return {}
