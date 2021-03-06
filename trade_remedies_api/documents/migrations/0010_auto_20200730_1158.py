# Generated by Django 2.2.6 on 2020-07-30 10:58

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("documents", "0009_auto_20200723_1026"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="blocked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="document",
            name="blocked_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="documents_blocked_by",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
