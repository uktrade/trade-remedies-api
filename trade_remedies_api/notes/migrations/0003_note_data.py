# Generated by Django 2.2.6 on 2020-02-21 09:57

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notes", "0002_note_model_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="note",
            name="data",
            field=django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True),
        ),
    ]
