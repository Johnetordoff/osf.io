from website.util import web_url_for
from addons.base.serializer import StorageAddonSerializer
from addons.s3 import utils
import boto3


class S3Serializer(StorageAddonSerializer):
    addon_short_name = 's3'

    REQUIRED_URLS = []

    @property
    def addon_serialized_urls(self):
        node = self.node_settings.owner
        user_settings = self.node_settings.user_settings or self.user_settings

        result = {
            'accounts': node.api_url_for('s3_account_list'),
            'createBucket': node.api_url_for('create_bucket'),
            'importAuth': node.api_url_for('s3_import_auth'),
            'create': node.api_url_for('s3_add_user_account'),
            'deauthorize': node.api_url_for('s3_deauthorize_node'),
            'folders': node.api_url_for('s3_folder_list'),
            'config': node.api_url_for('s3_set_config'),
            'files': node.web_url_for('collect_file_trees'),
        }
        if user_settings:
            result['owner'] = web_url_for('profile_view_id',
                uid=user_settings.owner._id)
        return result

    def serialized_folder(self, node_settings):
        return {
            'path': node_settings.folder_id,
            'name': node_settings.folder_name
        }

    def credentials_are_valid(self, user_settings, client=None):
        if user_settings:
            for account in user_settings.external_accounts.all():
                if utils.can_list(account.oauth_key, account.oauth_secret):
                    return True
        return False

    def serialize_settings(self, node_settings, current_user, client=None):
        result = super().serialize_settings(node_settings, current_user, client)
        user_settings = node_settings.user_settings

        if self.credentials_are_valid and user_settings:
            aws_access_key_id = user_settings.external_accounts.first().oauth_key
            aws_secret_key_id = user_settings.external_accounts.first().oauth_secret
            session = boto3.Session(
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_key_id
            )

            default_region_name = 'us-east-1'
            ssm_client = boto3.client(
                'ssm',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_key_id,
                region_name=default_region_name
            )

            data = []
            for location in session.get_available_regions('s3'):
                item = {}
                ssm_response = ssm_client.get_parameter(
                    Name='/aws/service/global-infrastructure/regions/%s/longName' % location
                )
                item['region_name'] = ssm_response['Parameter']['Value']
                item['region_id'] = location
                data.append(item)

            result['bucket_locations'] = data
        return result