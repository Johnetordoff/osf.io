# from django.contrib import admin

# Register your models here.

from django.contrib import admin
from web.models.user import Block, Schema
from django import forms
from django.utils.html import format_html
from django.db import models


class AdminSchema(admin.ModelAdmin):
    readonly_fields = ("link", "atomic_schema_link", "import_link")

    def link(self, obj):
        return format_html(f'<a href="{obj.link}">Schema JSON</a>')

    def import_link(self, obj):
        return format_html(
            f'<a href="{obj.import_link}" class="btn-success">Import CSV</a>'
        )

    def atomic_schema_link(self, obj):
        return format_html(f'<a href="{obj.atomic_schema_link}">Schema JSON</a>')

    link.allow_tags = True


class AdminPage(admin.ModelAdmin):
    class PageForm(forms.ModelForm):
        description = forms.CharField(
            widget=forms.Textarea(attrs={"rows": 5, "cols": 100}), required=False
        )

    form = PageForm


class AdminBlock(admin.ModelAdmin):
    ordering = ("index",)

    class QuestionForm(forms.ModelForm):
        block_type = forms.ChoiceField(choices=Block.SCHEMABLOCKS)
        help = forms.CharField(
            widget=forms.Textarea(attrs={"rows": 5, "cols": 100}),
            required=False,
            help_text="AKA help_text",
        )

    form = QuestionForm


admin.site.register(Block, AdminBlock)
admin.site.register(Schema, AdminSchema)
