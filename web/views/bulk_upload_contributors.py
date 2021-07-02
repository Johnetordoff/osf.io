from django.shortcuts import render, reverse, redirect, HttpResponse
from django.views import generic
from web.forms.forms import BulkUploadContributorsForm
from web.utils import get_paginated_data
import csv
from app import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy


class BulkUploadContributors(LoginRequiredMixin, generic.TemplateView, generic.FormView):
    template_name = "bulk_upload_contributor/bulk_upload_contributors.html"
    form_class = BulkUploadContributorsForm
    login_url = reverse_lazy('osf_oauth')

    def get_context_data(self, *args, **kwargs):
        user = self.request.user

        form = self.form_class(
            initial={
                'contributors_csv': user.bulk_contributors_csv,
            }
        )
        form.fields['node_id'].choices = self.get_node_choices(user)

        return {
            'form': form,
        }

    def get_node_choices(self, user):
        import asyncio
        url = f'{settings.OSF_API_URL}v2/users/{user.guid}/nodes/'
        data = asyncio.run(get_paginated_data(user.token, url))
        choices = []
        for node in data:
            choice = (node['id'], f'{node["attributes"]["title"]} ({node["id"]})')
            choices.append(choice)

        return choices

    def post(self, request, *args, **kwargs):
        form = BulkUploadContributorsForm(request.POST, request.FILES)
        user = request.user
        form.fields['node_id'].choices = self.get_node_choices(user)
        if user.bulk_contributors_csv:
            form.fields['contributors_csv'].required = False

        if form.is_valid():
            user.bulk_contributors_csv = form.cleaned_data['contributors_csv'] or user.bulk_contributors_csv
            user.save()
            csv_rows = self.parse_csv(user.bulk_contributors_csv)

        else:
            raise Exception(form.__dict__)
        return redirect(reverse('bulk_upload_contributors'))

    def get_success_url(self):
        return reverse('bulk_upload_contributors')

    def parse_csv(self, file):
        with open(file.name, 'wb') as csvfile:
            return csv.DictReader(csvfile)

