# Generated by Django 3.2.14 on 2022-08-31 13:35

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('invitations', '0014_invitation_invitation_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='invited_user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='invited_user', to=settings.AUTH_USER_MODEL),
        ),
    ]