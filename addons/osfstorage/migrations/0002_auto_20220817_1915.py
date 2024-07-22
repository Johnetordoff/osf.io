# Generated by Django 1.11.29 on 2022-08-17 19:15

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('osf', '0001_initial'),
        ('addons_osfstorage', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersettings',
            name='owner',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addons_osfstorage_user_settings', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='region',
            unique_together={('_id', 'name')},
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='owner',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='addons_osfstorage_node_settings', to='osf.AbstractNode'),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='region',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='addons_osfstorage.Region'),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='root_node',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='osf.OsfStorageFolder'),
        ),
        migrations.AddField(
            model_name='nodesettings',
            name='user_settings',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='addons_osfstorage.UserSettings'),
        ),
    ]
