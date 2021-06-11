# from django.contrib import admin

# Register your models here.

from django.contrib import admin
from web.models.user import Page, Question, Schema
from django import forms
from django.utils.html import format_html


class AdminSchema(admin.ModelAdmin):
    readonly_fields = ('to_json', 'link', )

    def link(self, obj):
        return format_html(f'<a href="{obj.link}">Schema JSON</a>')
    link.allow_tags = True



class AdminPage(admin.ModelAdmin):
    class PageForm(forms.ModelForm):
        description = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'cols': 100}), required=False)

    form = PageForm



class AdminQuestion(admin.ModelAdmin):
    class QuestionForm(forms.ModelForm):
        format = forms.ChoiceField(choices=Question.WIDGET_CHOICES)
        help = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'cols': 100}), required=False, help_text='AKA help_text')
        description = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'cols': 100}), required=False, help_text='AKA Instruction_text')

    form = QuestionForm



admin.site.register(Page, AdminPage)
admin.site.register(Question, AdminQuestion)
admin.site.register(Schema, AdminSchema)
