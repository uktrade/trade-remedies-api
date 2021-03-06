# Generated by Django 2.0.1 on 2018-10-15 14:44

import audit.models
import dirtyfields.dirtyfields
from django.db import migrations, models
import django.db.models.deletion
import django_countries.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("cases", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CaseContact",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_modified", models.DateTimeField(auto_now=True, null=True)),
                ("primary", models.BooleanField(default=False)),
            ],
            bases=(
                models.Model,
                dirtyfields.dirtyfields.DirtyFieldsMixin,
                audit.mixins.AuditableMixin,
            ),
        ),
        migrations.CreateModel(
            name="Contact",
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
                ("name", models.CharField(max_length=250)),
                ("email", models.EmailField(blank=True, max_length=254, null=True)),
                ("phone", models.CharField(blank=True, max_length=80, null=True)),
                ("address", models.TextField(blank=True, null=True)),
                ("post_code", models.CharField(blank=True, max_length=16, null=True)),
                (
                    "country",
                    django_countries.fields.CountryField(blank=True, max_length=2, null=True),
                ),
            ],
            options={"abstract": False,},
            bases=(
                models.Model,
                dirtyfields.dirtyfields.DirtyFieldsMixin,
                audit.mixins.AuditableMixin,
            ),
        ),
        migrations.CreateModel(
            name="ContactUser",
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
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="cases.Case"),
                ),
                (
                    "contact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="contacts.Contact"
                    ),
                ),
            ],
            options={"abstract": False,},
            bases=(
                models.Model,
                dirtyfields.dirtyfields.DirtyFieldsMixin,
                audit.mixins.AuditableMixin,
            ),
        ),
    ]
