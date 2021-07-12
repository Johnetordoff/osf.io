from django.forms import ModelForm, Form
from web.models import User
from django import forms


class SignupForm(ModelForm):
    class Meta:
        model = User
        fields = ["username", "password"]


class BulkUploadContributorsForm(Form):
    contributors_csv = forms.FileField(required=True, widget=forms.ClearableFileInput())
    node_id = forms.ChoiceField(required=True)
