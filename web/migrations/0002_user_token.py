# Generated by Django 3.1.1 on 2021-06-08 14:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='token',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
