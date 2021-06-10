from django.contrib.auth.models import AbstractUser
from my_secrets.secrets import OSF_OAUTH_CLIENT_ID, OSF_OAUTH_SECRET_KEY
import urllib
import requests
from app import settings
from django.db.models import CharField

class User(AbstractUser):
    token = CharField(null=True, blank=True, max_length=500)

    @classmethod
    def from_osf_login(cls, code):

        query_params = {
            'redirect_uri': settings.OSF_REDIRECT_URI,
            'client_id': OSF_OAUTH_CLIENT_ID,
            'client_secret': OSF_OAUTH_SECRET_KEY,
            'grant_type': 'authorization_code',
            'code': code
        }
        query_params = urllib.parse.urlencode(query_params)
        url = f'{settings.OSF_CAS_URL}oauth2/token?'
        url += query_params
        resp = requests.post(url)
        token = resp.json()['access_token']

        resp = requests.get(settings.OSF_API_URL + 'v2/', headers={'Authorization': f'Bearer {token}'})
        fullname = resp.json()['meta']['current_user']['data']['attributes']['full_name']

        user, created = cls.objects.get_or_create(username=fullname)
        user.token = token

        if created:
            user.save()


        return user