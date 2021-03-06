# Generated by Django 2.2.13 on 2021-01-24 17:40
import logging

from django.db import migrations

from audit.models import Audit


logger = logging.getLogger(__name__)


def set_case_title(apps, schema_editor):  # noqa
    logger.info(f"Found {Audit.objects.all().count()} audit log entries")
    audits = Audit.objects.all().iterator()
    titled = 0
    logger.info(f"Patching audit log case titles...")
    for audit in audits:
        if audit.case_title:
            titled += 1
        audit.save()
    logger.info(f"Precomputed case titles for {titled} audit log entries")


def unset_case_title(apps, schema_editor):  # noqa
    count = Audit.objects.all().count()
    logger.info(f"Found {count} audit log entries")
    audits = Audit.objects.all().iterator()
    logger.info(f"Removing precomputed audit log case titles...")
    for audit in audits:
        audit.data.pop("case_title", "")
        audit.save()
    logger.info(f"Removed case titles for {count} audit log entries")


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0009_auto_20200212_1428'),
    ]

    operations = [
        migrations.RunPython(set_case_title, reverse_code=unset_case_title)
    ]
