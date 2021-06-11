from django.contrib.auth.models import AbstractUser
from my_secrets.secrets import OSF_OAUTH_CLIENT_ID, OSF_OAUTH_SECRET_KEY
import urllib
import requests
from app import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.shortcuts import render, reverse, redirect, HttpResponse


class User(AbstractUser):
    token = models.CharField(null=True, blank=True, max_length=500)
    admin = models.BooleanField(null=True, blank=True)

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
        user_data = resp.json()
        fullname = user_data['meta']['current_user']['data']['attributes']['full_name']

        user, created = cls.objects.get_or_create(username=fullname)
        user.token = token
        user.set_password('science')

        user.is_superuser = True
        user.is_staff = True

        if created:
            user.save()


        return user


class Schema(models.Model):
    name = models.CharField(max_length=500, blank=True, null=True)
    version = models.PositiveIntegerField()
    description = models.CharField(max_length=5000, blank=True, null=True)

    user = models.ForeignKey('web.User', on_delete=models.SET_NULL, null=True, related_name='schemas')

    def __str__(self):
        return f'{self.name} v{self.version}'

    @property
    def link(self):
        return 'https://emu.ngrok.io' + reverse('schema_json', args=(self.id, ))

    @property
    def to_json(self):
        data = {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'pages': []
        }
        pages = self.pages.all().order_by('number')

        for page in pages:
            data['pages'].append(page.to_json)

        return data


class Page(models.Model):
    title = models.CharField(max_length=500)
    description = models.CharField(max_length=5000, null=True, blank=True)
    number = models.PositiveIntegerField()
    schema = models.ForeignKey('web.Schema', on_delete=models.SET_NULL, null=True, related_name='pages')

    def __str__(self):
        return f'Page {self.number} of {self.schema.name}'

    @property
    def to_json(self):
        data = {
            'id': f'page{self.number}',
            'title': self.title,
            'questions': [],
        }
        if self.description:
            data['description'] = self.description

        questions = self.questions.order_by('number')
        for question in questions:
            data['questions'].append(question.to_json)

        return data

    class Meta:
        unique_together = ('schema', 'number',)



class Question(models.Model):
    WIDGET_TYPES = {
        'text': 'string',
        'textarea': 'string',
        'osf-upload': 'osf-upload',
        'osf-upload-with-textarea': 'osf-upload',
        'osf-upload-open': 'osf-upload',
        'multiselect': 'choose',
        'singleselect': 'choose'
    }
    WIDGET_CHOICES = [
        ('text', 'Single line text box'),
        ('textarea', 'Text area'),
        ('osf-upload', 'Upload Widget'),
        ('osf-upload-with-textarea', 'Upload Widget with Textarea'),
        ('osf-upload-open', 'Upload Widget (Opened)'),
        ('multiselect', 'Multiselect'),
        ('singleselect', 'Single select')
    ]
    SCHEMABLOCKS = [
        ('page-heading', 'page-heading'),
        ('section-heading', 'section-heading'),
        ('subsection-heading', 'subsection-heading'),
        ('paragraph', 'paragraph'),
        ('question-label', 'question-label'),
        ('short-text-input', 'short-text-input'),
        ('long-text-input', 'long-text-input'),
        ('file-input', 'file-input'),
        ('contributors-input', 'contributors-input'),
        ('single-select-input', 'single-select-input'),
        ('multi-select-input', 'multi-select-input'),
        ('select-input-option', 'select-input-option'),
        ('select-other-option', 'select-other-option'),
    ]

    nav = models.CharField(max_length=5000, null=True, blank=True)
    help = models.CharField(max_length=5000, null=True, blank=True, help_text='AKA help_text')
    title = models.CharField(max_length=5000, null=True, blank=True, help_text='AKA Display_text')
    header = models.CharField(max_length=5000, null=True, blank=True)
    description = models.CharField(max_length=5000, null=True, blank=True, help_text='AKA instruction_text')
    format = models.CharField(choices=WIDGET_CHOICES, max_length=50000, null=True, blank=True)
    page = models.ForeignKey('web.Page', on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    options = ArrayField(models.CharField(max_length=100), null=True, blank=True, help_text='Enter as comma seperated list')
    required = models.BooleanField(null=True)
    add_textarea_to_uploader = models.BooleanField(null=True, help_text='This only does something in you are using a file uploader')
    number = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f'Question #{self.number} of {self.page}'

    class Meta:
        unique_together = ('page', 'number',)


    @property
    def to_json(self):
        if self.header:
            data = {
                "qid": f"q{self.page.number}-{self.number}",
                "type": "object",
                "title": self.header
            }
            if self.nav:
                data['nav'] = self.nav

            data["properties"] = {
                "id": f"prop{self.number}",
                "type": self.WIDGET_TYPES[self.format],
                "format": self.format,
                "required": self.required,
                "title": self.title
            }

            if self.description:
                data['properties'] = {'description': self.description}


            if self.WIDGET_TYPES[self.format] == 'choose':
                data["properties"]['options'] = self.options
            else:
                data["properties"]['format'] = self.format
                data["properties"]['type'] = self.WIDGET_TYPES[self.format]
        else:
            data = {
                "qid": f"q{self.number}",
                'help': self.help,
                'required': self.required,
                'title': self.title
            }
            if self.nav:
                data['nav'] = self.nav

            if self.description:
                data['description'] = self.description

            if self.WIDGET_TYPES[self.format] == 'choose':
                data['options'] = self.options
                data['format'] = self.format
                data['type'] = self.WIDGET_TYPES[self.format]
            elif self.WIDGET_TYPES[self.format] == 'osf-upload':
                data["properties"] = [
                    {
                    "id": "uploader",
                    "type": self.WIDGET_TYPES[self.format],
                    "format": self.format
                }]
                if self.format == "osf-upload-with-textarea" or self.add_textarea_to_uploader:
                    data["properties"].insert(0, {
                        "id": "question",
                        "type": "string",
                        "format": "textarea",
                        "required": self.required
                    })
            else:
                data['format'] = self.format
                data['type'] = self.WIDGET_TYPES[self.format]

        return data