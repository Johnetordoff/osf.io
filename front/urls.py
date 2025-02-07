from django.urls import re_path

from front import views

app_name = 'osf'

urlpatterns = [
    re_path(r'forgot-password$', views.ResetPasswordView.as_view(), name='reset_password'),
]
