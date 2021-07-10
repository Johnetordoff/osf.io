from django.shortcuts import render, reverse, redirect, HttpResponse
from django.views import generic
from web.forms.forms import BulkUploadContributorsForm
from web.utils import get_paginated_data
import csv
from app import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
import requests
from django.contrib import messages

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
            payload = self.format_payload(csv_rows)
            self.send_payload(payload, form.cleaned_data['node_id'], user)

        else:
            raise Exception(form.__dict__)
        return redirect(reverse('bulk_upload_contributors'))

    def get_success_url(self):
        return reverse('bulk_upload_contributors')

    def parse_csv(self, file):
        with open(file.name, newline='') as csvfile:
            return list(csv.DictReader(csvfile))

    def format_payload(self, data):
        payloads = []
        for row in data:
            payloads.append(({
                'data': {
                    'type': 'contributors',
                    'attributes': {
                        'full_name': row.get('full_name'),
                        'email': row.get('email'),
                        'bibliographic': True if row.get('bibliographic') else False,
                        'permission': row.get('permissions'),
                        'index': row.get('_order'),
                    }
                }
            }, row["send_email"]))
        return payloads

    def send_payload(self, data, node_id, user):
        for payload, send_email in data:
            resp = requests.post(
                f'{settings.OSF_API_URL}v2/nodes/{node_id}/contributors/?send_email={"default" if send_email == "TRUE" else "false"}',
                json=payload,
                headers={
                    'Authorization': f'Bearer {user.token}'
                }
            )

            if resp.status_code == 400:
                data = resp.json()
                errors = data['errors']
                for error in errors:
                    messages.add_message(self.request, messages.ERROR, error['detail'])

