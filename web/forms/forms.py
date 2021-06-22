from django.forms import ModelForm
from web.models import User


class SignupForm(ModelForm):
    class Meta:
        model = User
        fields = ["username", "password"]
