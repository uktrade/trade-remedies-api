# Generated by Django 2.0.1 on 2018-10-15 14:44

import audit.models
import dirtyfields.dirtyfields
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("cases", "0002_auto_20181015_1444"),
        ("auth", "0009_alter_user_last_name_max_length"),
        ("organisations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CaseAction",
            fields=[
                ("id", models.CharField(max_length=50, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name="CaseRole",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("key", models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ("order", models.SmallIntegerField(default=0)),
                ("plural", models.CharField(blank=True, max_length=100, null=True)),
                ("actions", models.ManyToManyField(to="security.CaseAction")),
            ],
        ),
        migrations.CreateModel(
            name="OrganisationCaseRole",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True, null=True)),
                ("sampled", models.BooleanField(default=False)),
                ("non_responsive", models.BooleanField(default=False)),
                (
                    "case",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="cases.Case"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="organisationcaserole_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="organisationcaserole_modified_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="organisations.Organisation"
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="security.CaseRole"
                    ),
                ),
            ],
            bases=(
                models.Model,
                dirtyfields.dirtyfields.DirtyFieldsMixin,
                audit.mixins.AuditableMixin,
            ),
        ),
        migrations.CreateModel(
            name="OrganisationUser",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True, null=True)),
                ("confirmed", models.BooleanField(default=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="organisationuser_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="organisationuser_modified_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="organisations.Organisation"
                    ),
                ),
                (
                    "security_group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="auth.Group",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            bases=(
                models.Model,
                dirtyfields.dirtyfields.DirtyFieldsMixin,
                audit.mixins.AuditableMixin,
            ),
        ),
        migrations.CreateModel(
            name="UserCase",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True, null=True)),
                (
                    "case",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="cases.Case"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="usercase_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "modified_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="usercase_modified_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "organisation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="organisations.Organisation",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            bases=(
                models.Model,
                dirtyfields.dirtyfields.DirtyFieldsMixin,
                audit.mixins.AuditableMixin,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="usercase", unique_together={("user", "case", "organisation")},
        ),
        migrations.AlterUniqueTogether(
            name="organisationuser", unique_together={("organisation", "user")},
        ),
        migrations.AlterUniqueTogether(
            name="organisationcaserole", unique_together={("organisation", "case")},
        ),
    ]
