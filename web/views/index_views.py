from django.shortcuts import render, reverse, redirect
from django.http.response import JsonResponse
from django.views import generic
from web.forms.forms import SignupForm
from web.models.user import User, Schema, Block
from django.contrib.auth import authenticate, login
from my_secrets.secrets import OSF_OAUTH_CLIENT_ID
import requests
from app.settings import OSF_REDIRECT_URI, OSF_CAS_URL, OSF_API_URL
from web.forms.schema_editor import SchemaForm, BlockForm

def index(request):
    return render(request, "index.html")


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


class BlockEditorView(generic.TemplateView, generic.FormView):
    template_name = "schema_editor/block_editor.html"
    form_class = BlockForm

    def get_context_data(self, *args, **kwargs):
        schema = Schema.objects.get(id=self.kwargs['schema_id'])

        form = SchemaForm(self.request.GET, self.request.FILES)

        return {
            'schema': schema,
            'blocks': Block.objects.filter(
                schema__user=self.request.user,
                schema_id=self.kwargs['schema_id']).order_by('index'),
            'block_types': [block_type[0] for block_type in Block.SCHEMABLOCKS]
        }


    def get_success_url(self):
        return reverse('block_editor', kwargs={'schema_id': Block.get(id=self.kwargs['block']).schema.id})

class SchemaJSONView(generic.View):

    def get(self, request, schema_id):
        return JsonResponse(Schema.objects.get(id=schema_id).to_json)


class SimpleSchemaJSONView(generic.View):

    def get(self, request, schema_id):
        return JsonResponse(Schema.objects.get(id=schema_id).to_atomic_schema)


class ImportView(generic.View):

    def get(self, request, schema_id):
        schema = Schema.objects.get(id=schema_id)
        with open(schema.csv.read(), 'r') as csvfile:
            data = csvfile.read()
            raise Exception(csvfile.read())
            data = csv.reader(csvfile.read(), delimiter=",")
            Question.objects.create(
                **data
            )


        return JsonResponse(Schema.objects.get(id=schema_id).to_atomic_schema)


class OSFOauthView(generic.TemplateView):
    def get(self, request):
        return redirect(
            f"{OSF_CAS_URL}oauth2/authorize/?client_id={OSF_OAUTH_CLIENT_ID}"
            f"&redirect_uri={OSF_REDIRECT_URI}"
            f"&scope=osf.full_write"
            f"&response_type=code"
        )


class OSFOauthCallbackView(generic.View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        user = User.from_osf_login(code)
        user.save()
        login(request, user)
        return redirect(reverse('schema_editor'))
