# Generated by Django 2.0.1 on 2018-12-13 16:06

from django.db import migrations
from django.db.models import F


def run(apps, schema_editor):
    Audit = apps.get_model("audit", "Audit")
    Audit.objects.update(case_id_new=F("case_temp_id"))


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0004_audit_case_id_new"),
    ]

    operations = [
        # migrations.RunPython(run),
    ]
