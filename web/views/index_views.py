from django.shortcuts import render, reverse, redirect, HttpResponse
from django.http.response import JsonResponse
from django.views import generic
from web.forms import SignupForm
from web.models.user import User, Schema, Question
from django.contrib.auth import authenticate, login
from my_secrets.secrets import OSF_OAUTH_CLIENT_ID, OSF_OAUTH_SECRET_KEY
import requests
from app.settings import OSF_REDIRECT_URI, OSF_CAS_URL, OSF_API_URL

def index(request):
    return render(request, "base.html", {"title": 1})


class SignupView(generic.FormView):
    template_name = "auth/sign_up.html"
    form_class = SignupForm

    def get_success_url(self):
        return reverse("users")

    def form_valid(self, form):
        username = form.cleaned_data["username"]
        user = User.objects.create_user(username=username)
        user.set_password('science')
        user.save()
        user = authenticate(username=username, password='science')
        if user:
            login(self.request, user)
        return super().form_valid(form)


class RegistrationView(generic.TemplateView):
    template_name = "registrations/register.html"

    def get(self, request):
        user = request.user
        resp = requests.get(OSF_API_URL + 'v2/users/me/registrations/', headers={'Authorization': f'Bearer {user.token}'})

        return render(request, self.template_name, {'data': resp.json()['data']})

class SchemaJSONView(generic.View):

    def get(self, request, schema_id):
        return JsonResponse(Schema.objects.get(id=schema_id).to_json)


class SimpleSchemaJSONView(generic.View):

    def get(self, request, schema_id):
        return JsonResponse(Schema.objects.get(id=schema_id).to_simple_schema)


class ImportView(generic.View):

    def get(self, request):
        CSVs = [schema.csv for schema in Schema.objects.all() if schema.csv]
        import csv
        for csv_file in CSVs:
            with open(csv_file.path, 'r') as csvfile:
                data = csvfile.read()
                raise Exception(csvfile.read())
                data = csv.reader(csvfile.read(), delimiter=",")
                Question.objects.create(
                    **data
                )


        return JsonResponse(Schema.objects.get(id=schema_id).to_simple_schema)


class OSFOauthView(generic.TemplateView):
    def get(self, request):
        from urllib.parse import quote
        return redirect(
            f"{OSF_CAS_URL}oauth2/authorize/?client_id={OSF_OAUTH_CLIENT_ID}"
            f"&redirect_uri={OSF_REDIRECT_URI}"
            f"&scope=osf.full_read"
            f"&response_type=code"
        )


class OSFOauthCallbackView(generic.View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        user = User.from_osf_login(code)
        user.save()
        login(request, user)
        return redirect(reverse('home'))
