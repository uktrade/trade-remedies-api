import logging

from django.db import migrations, models
from cases.models.submission import Submission

logger = logging.getLogger(__name__)


def submission_organisation_name(apps, schema_editor):
    subs = Submission.objects.all()
    for sub in subs:
        if not sub.organisation_name and sub.organisation:
            sub._disable_audit = True
            sub.organisation_name = sub.organisation.name
            sub.save()
            logger.info(f"Organisation name set to {sub.organisation_name}")


class Migration(migrations.Migration):

    dependencies = [
        ("organisations", "0008_organisation_fraudulent"),
        ("cases", "0039_auto_20190903_0817"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="organisation_name",
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.RunPython(submission_organisation_name),
    ]
