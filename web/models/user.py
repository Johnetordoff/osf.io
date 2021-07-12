from django.contrib.auth.models import AbstractUser
from my_secrets.secrets import OSF_OAUTH_CLIENT_ID, OSF_OAUTH_SECRET_KEY
import urllib
import requests
from app import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.shortcuts import render, reverse, redirect, HttpResponse
from django.db.models import CheckConstraint, Q, F, Case


class User(AbstractUser):
    guid = models.CharField(null=True, blank=True, max_length=500)
    token = models.CharField(null=True, blank=True, max_length=500)
    admin = models.BooleanField(null=True, blank=True)
    bulk_contributors_csv = models.FileField(
        null=True, blank=True, upload_to="csv/bulk_contributors/"
    )

    @classmethod
    def from_osf_login(cls, code):

        query_params = {
            "redirect_uri": settings.OSF_REDIRECT_URI,
            "client_id": OSF_OAUTH_CLIENT_ID,
            "client_secret": OSF_OAUTH_SECRET_KEY,
            "grant_type": "authorization_code",
            "code": code,
        }
        query_params = urllib.parse.urlencode(query_params)
        url = f"{settings.OSF_CAS_URL}oauth2/token?"
        url += query_params
        resp = requests.post(url)
        token = resp.json()["access_token"]

        resp = requests.get(
            settings.OSF_API_URL + "v2/", headers={"Authorization": f"Bearer {token}"}
        )
        user_data = resp.json()
        fullname = user_data["meta"]["current_user"]["data"]["attributes"]["full_name"]
        guid = user_data["meta"]["current_user"]["data"]["id"]

        user, created = cls.objects.get_or_create(username=fullname)
        user.token = token
        user.guid = guid
        user.set_password("science")

        user.is_superuser = True
        user.is_staff = True

        if created:
            user.save()

        return user


class Schema(models.Model):
    name = models.CharField(max_length=500, blank=True, null=True)
    version = models.PositiveIntegerField()
    description = models.CharField(max_length=5000, blank=True, null=True)
    csv = models.FileField(null=True, upload_to="csv/")

    user = models.ForeignKey(
        "web.User", on_delete=models.SET_NULL, null=True, related_name="schemas"
    )

    def __str__(self):
        return f"{self.name} v{self.version}"

    @property
    def link(self):
        return "https://emu.ngrok.io" + reverse("schema_json", args=(self.id,))

    @property
    def import_link(self):
        return "https://emu.ngrok.io" + reverse("import")

    @property
    def atomic_schema_link(self):
        return "https://emu.ngrok.io" + reverse("atomic_schema", args=(self.id,))

    def get_absolute_url(self):
        return reverse("block_editor", kwargs={"schema_id": self.id})

    @property
    def to_json(self):
        data = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "pages": [],
        }
        pages = self.pages.all().order_by("-index")

        for page in pages:
            data["pages"].append(page.to_json)

        return data

    def populate(self):
        print(self.csv)

    @property
    def to_atomic_schema(self):
        return {
            "atomicSchema": True,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "blocks": [
                block.to_atomic_schema_block
                for block in self.blocks.all().order_by("index")
            ],
        }


class Block(models.Model):
    WIDGET_TYPES = {
        "text": "string",
        "textarea": "string",
        "osf-upload": "osf-upload",
        "osf-upload-with-textarea": "osf-upload",
        "osf-upload-open": "osf-upload",
        "multiselect": "choose",
        "singleselect": "choose",
    }
    WIDGET_CHOICES = [
        ("text", "Single line text box"),
        ("textarea", "Text area"),
        ("osf-upload", "Upload Widget"),
        ("osf-upload-with-textarea", "Upload Widget with Textarea"),
        ("osf-upload-open", "Upload Widget (Opened)"),
        ("multiselect", "Multiselect"),
        ("singleselect", "Single select"),
    ]
    SCHEMABLOCKS = [
        ("page-heading", "Page Heading"),
        ("section-heading", "Section Heading"),
        ("subsection-heading", "Subsection Heading"),
        ("paragraph", "Paragraph"),
        ("question-label", "Question Label"),
        ("short-text-input", "Short Text Input"),
        ("long-text-input", "Long Text Input"),
        ("file-input", "File Input"),
        ("contributors-input", "Contributors Input"),
        ("single-select-input", "Single Select Input"),
        ("multi-select-input", "Multi-select Input"),
        ("select-input-option", "Select Input Option"),
        ("select-other-option", "Select Other Option"),
    ]

    nav = models.CharField(max_length=5000, null=True, blank=True, default="")
    help_text = models.CharField(
        max_length=5000, null=True, default="", blank=True, help_text="AKA help"
    )
    display_text = models.CharField(
        max_length=5000, null=True, blank=True, default="", help_text="AKA title"
    )
    example_text = models.CharField(
        max_length=5000, null=True, blank=True, default="", help_text="AKA example"
    )
    block_type = models.CharField(
        choices=SCHEMABLOCKS, max_length=50000, null=True, blank=True
    )
    schema = models.ForeignKey(
        "web.Schema",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocks",
    )
    options = ArrayField(
        models.CharField(max_length=100),
        null=True,
        blank=True,
        help_text="Enter as comma separated list",
    )
    required = models.BooleanField(null=True)
    index = models.PositiveIntegerField(null=True)

    def __str__(self):
        return f"#{self.index} - {self.block_type}"

    class Meta:
        unique_together = (
            "schema",
            "index",
        )

        constraints = []

    @property
    def to_atomic_schema_block(self):
        return {
            "help_text": self.help_text or "",
            "block_type": self.block_type,
            "display_text": self.display_text or "",
            "example_text": self.example_text or "",
            "required": bool(self.required),
        }

    @property
    def to_block(self):
        return {
            "schema_id": self.schema.id,
            "help_text": self.help_text,
            "example_text": self.example_text,
            "registration_response_key": f"q{self.index}",
            "block_type": self.block_type,
            "display_text": self.display_text,
            "required": self.required,
        }
