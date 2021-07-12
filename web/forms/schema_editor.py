from django.forms import ModelForm
from web.models.user import Schema, Block
from django import forms


class SchemaForm(ModelForm):
    name = forms.CharField(max_length=100, required=False)
    version = forms.IntegerField(required=False)
    csv = forms.FileField(widget=forms.ClearableFileInput(), required=False)

    class Meta:
        model = Schema
        fields = ["name", "version", "csv"]


class BlockForm(ModelForm):
    help_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="This is shown only on question labels",
    )
    block_type = forms.ChoiceField(choices=Block.SCHEMABLOCKS, required=True)
    example_text = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="This is shown only on question labels",
    )
    display_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control"}),
        help_text="This is shown on all non-input block types",
    )

    required = forms.BooleanField(required=False)
    nav = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Not sure what this does.",
    )
    index = forms.IntegerField(required=False)

    class Meta:
        model = Block
        fields = [
            "nav",
            "help_text",
            "display_text",
            "example_text",
            "block_type",
            "required",
            "index",
        ]
