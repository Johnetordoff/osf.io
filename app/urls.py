"""app URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.contrib import admin
from web.views.index_views import index, SignupView, OSFOauthCallbackView, OSFOauthView, SimpleSchemaJSONView, SchemaJSONView, ImportView
from django.conf.urls import url, include

urlpatterns = [
    url(r"^$", index, name="home"),
    url("^", include("django.contrib.auth.urls")),
    url(r"^admin/", admin.site.urls, name="admin_app"),
    url(r"^sign_up/$", SignupView.as_view(), name="sign_up"),
    url(r"^osf_oauth/$", OSFOauthView.as_view(), name="osf_oauth"),
    url(r"^callback/$", OSFOauthCallbackView.as_view(), name="callback"),
    url(r"^(?P<schema_id>\w+)/json/$", SchemaJSONView.as_view(), name="schema_json"),
    url(r"^(?P<schema_id>\w+)/json/simpleschema/$", SimpleSchemaJSONView.as_view(), name="simple_schema"),
    url(r"^import/$", ImportView.as_view(), name="import"),
]
