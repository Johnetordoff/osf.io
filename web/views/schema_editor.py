import requests
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView
from django.views.generic import TemplateView
from web.models.user import Schema, Block
from django.shortcuts import render, reverse, redirect
from web.forms.schema_editor import SchemaForm, BlockForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from app import settings

class SchemaCreateView(LoginRequiredMixin, CreateView):
    model = Schema
    fields = ['name', 'version']

    def post(self, request, *args, **kwargs):
        form = SchemaForm(request.POST)

        if form.is_valid():
            schema = form.save()
            schema.user = request.user
            schema.save()
        else:
            raise Exception(form.__dict__)
        return redirect(reverse('schema_editor'))


class SchemaUpdateView(LoginRequiredMixin, UpdateView):
    pk_url_kwarg = 'schema_id'

    model = Schema

    def post(self, request, *args, **kwargs):
        form = SchemaForm(request.POST, request.FILES)
        if form.is_valid():
            Schema.objects.filter(id=self.kwargs['schema_id']).update(**form.cleaned_data)
            csv = request.FILES.get('csv')
            schema = Schema.objects.get(id=self.kwargs['schema_id'])
            schema.csv = csv
            schema.save()
            if csv:
                self.read_csv(schema.csv)
        else:
            raise Exception(form.__dict__)
        return redirect(reverse('block_editor', kwargs={'schema_id': self.kwargs['schema_id']}))

    def read_csv(self, file):
        import csv
        with open(file.name, 'r') as fp:
            spamreader = csv.reader(fp, delimiter=',')
            for row in spamreader:
                data = row[0]




class SchemaDeleteView(LoginRequiredMixin, DeleteView):
    model = Schema
    success_url = reverse_lazy('schema_editor')
    pk_url_kwarg = 'schema_id'


class BlockCreateView(LoginRequiredMixin, CreateView):
    model = Block
    fields = ['display_text', 'block_type']

    def post(self, request, *args, **kwargs):
        form = BlockForm(request.POST)
        if form.is_valid():
            block = Block(**form.cleaned_data)
            block.schema_id = self.kwargs['schema_id']
            block.user = request.user
            block.save()
            block.index = block.schema.blocks.count() + 1
            block.save()
        else:
            raise Exception(form.__dict__)
        return redirect(reverse('block_editor', kwargs={'schema_id': self.kwargs['schema_id']}))


class BlockUpdateView(LoginRequiredMixin, UpdateView, FormView):
    model = Block
    success_url = reverse_lazy('block_editor')
    pk_url_kwarg = 'block_id'
    template_name = "schema_editor/change_block.html"
    form_class = BlockForm

    def get_context_data(self, *args, **kwargs):
        block = self.get_object()
        form = self.form_class(
            initial={
                'display_text': block.display_text,
                'block_type': block.block_type,
                'required': block.required,
                'index': block.index,
            }
        )
        form.display_text = self.get_object().display_text
        form.block_type = self.get_object().block_type

        return {
            'block_id': self.kwargs['block_id'],
            'schema_id': self.kwargs['schema_id'],
            'form': form,
        }

    def get_success_url(self):
        return reverse('block_editor', kwargs={'schema_id': self.kwargs['schema_id']})



class BlockDeleteView(LoginRequiredMixin, DeleteView):
    model = Block
    pk_url_kwarg = 'block_id'

    def get_success_url(self):
        return reverse('block_editor', kwargs={'schema_id': self.kwargs['schema_id']})



class SchemaEditorView(LoginRequiredMixin, TemplateView, FormView):
    template_name = "schema_editor/schema_editor.html"
    form_class = SchemaForm
    login_url = reverse_lazy('osf_oauth')

    def get_context_data(self, *args, **kwargs):
        return {'schemas': Schema.objects.filter(user=self.request.user) }

    def get_success_url(self):
        return reverse('schema_editor')


