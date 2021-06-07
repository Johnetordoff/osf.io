from django.shortcuts import render, reverse
from django.views import generic
from web.forms import SignupForm
from web.models import User
from django.contrib.auth import authenticate, login


def index(request):
    return render(request, "base.html", {"title": 1})


class SignupView(generic.FormView):
    template_name = "auth/sign_up.html"
    form_class = SignupForm

    def get_success_url(self):
        return reverse("users")

    def form_valid(self, form):
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        user = User.objects.create_user(username=username)
        user.set_password(password)
        user.save()
        user = authenticate(username=username, password=password)
        if user:
            login(self.request, user)
        return super().form_valid(form)
