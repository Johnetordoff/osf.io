# Generated by Django 3.2.17 on 2024-06-21 16:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osf', '0020_abstractprovider_advertise_on_discover_page'),
    ]

    operations = [
        migrations.AddField(
            model_name='preprint',
            name='affiliated_institutions',
            field=models.ManyToManyField(related_name='preprints', to='osf.Institution'),
        ),
    ]
