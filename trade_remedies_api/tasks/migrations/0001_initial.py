# Generated by Django 2.2.6 on 2020-01-22 18:25

import audit.mixins
import dirtyfields.dirtyfields
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cases", "0049_auto_20200120_1341"),
    ]

    operations = [
        migrations.CreateModel(
            name="Task",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True, null=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(blank=True, max_length=250, null=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("model_id", models.UUIDField()),
                ("model_key", models.CharField(blank=True, max_length=250, null=True)),
                ("due_date", models.DateTimeField(null=True)),
                ("estimated_duration", models.IntegerField(null=True)),
                ("priority", models.CharField(blank=True, max_length=20, null=True)),
                (
                    "assignee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="task_assignee",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "case",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="cases.Case",
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="contenttypes.ContentType"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="task_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="task_modified_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"index_together": {("content_type", "model_id")},},
            bases=(
                models.Model,
                dirtyfields.dirtyfields.DirtyFieldsMixin,
                audit.mixins.AuditableMixin,
            ),
        ),
    ]
