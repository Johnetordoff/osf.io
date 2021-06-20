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
    csv = models.FileField(null=True, blank=True)

    user = models.ForeignKey('web.User', on_delete=models.SET_NULL, null=True, related_name='schemas')

    def __str__(self):
        return f'{self.name} v{self.version}'

    @property
    def link(self):
        return 'https://emu.ngrok.io' + reverse('schema_json', args=(self.id, ))

    @property
    def import_link(self):
        return 'https://emu.ngrok.io' + reverse('import')

    @property
    def simple_schema_link(self):
        return 'https://emu.ngrok.io' + reverse('simple_schema', args=(self.id, ))

    @property
    def to_json(self):
        data = {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'pages': []
        }
        pages = self.pages.all().order_by('-number')

        for page in pages:
            data['pages'].append(page.to_json)

        return data


    def populate(self):
        print(self.csv)

    @property
    def to_simple_schema(self):

        question_ids = self.pages.all().values_list('questions__id').distinct()

        return {
            'simpleschema': True,
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'blocks': [block.to_simple_schema_block for block in Question.objects.filter(id__in=question_ids).order_by('page__number', 'number')]
        }



class Page(models.Model):
    number = models.PositiveIntegerField()
    schema = models.ForeignKey('web.Schema', on_delete=models.SET_NULL, null=True, related_name='pages')

    # constraint to page header
    def __str__(self):
        return f'Page {self.number} of {self.schema.name}'

    @property
    def to_json(self):
        page_headers = self.questions.order_by('number')[0]
        page_data = {
            'id': f'page{self.number}',
            'type': 'textarea',
            'title': page_headers.display_text,
            'description': page_headers.help_text,
            'questions': [{}],
        }

        questions = self.questions.order_by('number')[1:]
        for question in questions:
            if question.format == 'section-heading':
                page_data['questions'][0]['properties'] = [question.to_json]

            page_data['questions'].append(question.to_json)


        return page_data

    class Meta:
        unique_together = ('schema', 'number',)

from django.db import models
from django.db.models import CheckConstraint, Q, F, Case


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
        ('page-heading', 'Page Heading'),
        ('section-heading', 'Section Heading'),
        ('subsection-heading', 'Subsection Heading'),
        ('paragraph', 'Paragraph'),
        ('question-label', 'Question Label'),
        ('short-text-input', 'Short Text Input'),
        ('long-text-input', 'Long Text Input'),
        ('file-input', 'File Input'),
        ('contributors-input', 'Contributors Input'),
        ('single-select-input', 'Single Select Input'),
        ('multi-select-input', 'Multi-select Input'),
        ('select-input-option', 'Select Input Option'),
        ('select-other-option', 'Select Other Option'),
    ]

    nav = models.CharField(max_length=5000, null=True, blank=True)
    help_text = models.CharField(max_length=5000, null=True, blank=True, help_text='AKA help')
    display_text = models.CharField(max_length=5000, null=True, blank=True, help_text='AKA title')
    example_text = models.CharField(max_length=5000, null=True, blank=True, help_text='AKA example')
    format = models.CharField(choices=SCHEMABLOCKS, max_length=50000, null=True, blank=True)
    page = models.ForeignKey('web.Page', on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    options = ArrayField(models.CharField(max_length=100), null=True, blank=True, help_text='Enter as comma separated list')
    required = models.BooleanField(null=True)
    add_textarea_to_uploader = models.BooleanField(null=True, help_text='This only does something in you are using a file uploader')
    number = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f'#{self.number} of {self.page} - {self.format}'

    class Meta:
        unique_together = ('page', 'number',)

        constraints = [
            CheckConstraint(
                check=~Q(format='page-heading') | Q(format='page-heading', help_text__isnull=True, example_text__isnull=True),
                name='check_page_heading',
            ),
            CheckConstraint(
                check=~Q(format='section-heading') | Q(format='section-heading', help_text__isnull=True, example_text__isnull=True),
                name='check_section_heading',
            ),
            CheckConstraint(
                check=~Q(format='file-input') | Q(
                    format='file-input',
                    display_text__isnull=True,
                    help_text__isnull=True,
                    example_text__isnull=True
                ),
                name='check_file_input',
            ),
        ]

    FORMAT_TYPE_TO_TYPE_MAP = {
        ('multiselect', 'choose'): 'multi-select-input',
        (None, 'multiselect'): 'multi-select-input',
        (None, 'choose'): 'single-select-input',
        ('osf-upload-open', 'osf-upload'): 'file-input',
        ('osf-upload-toggle', 'osf-upload'): 'file-input',
        ('singleselect', 'choose'): 'single-select-input',
        ('text', 'string'): 'short-text-input',
        ('textarea', 'osf-author-import'): 'contributors-input',
        ('textarea', None): 'long-text-input',
        ('textarea', 'string'): 'long-text-input',
        ('textarea-lg', None): 'long-text-input',
        ('textarea-lg', 'string'): 'long-text-input',
        ('textarea-xl', 'string'): 'long-text-input',
    }
    FORMAT_TYPE_TO_TYPE_MAP = {
        'multi-select-input': 'choose',
        'single-select-input': 'choose',
        'file-input': 'osf-upload',
        'short-text-input': ('text', 'string'),
        'contributors-input': ('textarea', 'osf-author-import'),
        'long-text-input': ('textarea', 'string'),
    }

    @property
    def to_atomic_schema_block(self):
        return {
             'help_text': self.help_text,
             'block_type': self.format,
             'display_text': self.display_text,
             'example_text': self.example_text,
             'required': bool(self.required),
        }

    @property
    def to_block(self):
        return {
             'schema_id': self.page.schema.id,
             'help_text': self.help_text,
             'example_text': self.example_text,
             'registration_response_key': f'q{self.page.number}-{self.number}',
             'block_type': self.format,
             'display_text': self.display_text,
             'required': self.required,
        }
