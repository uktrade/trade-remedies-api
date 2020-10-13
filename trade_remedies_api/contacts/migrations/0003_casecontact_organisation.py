import logging

from django.db import migrations, models
import django.db.models.deletion
from contacts.models import CaseContact

logger = logging.getLogger(__name__)


def case_contact_org(apps, schema_editor):
    casecontacts = CaseContact.objects.all()
    for casecontact in casecontacts:
        logger.info(f"-> {casecontact}")
        casecontact._disable_audit = True
        casecontact.organisation = casecontact.contact.organisation
        casecontact.save()


class Migration(migrations.Migration):

    dependencies = [
        ("organisations", "0003_auto_20181211_1642"),
        ("contacts", "0002_auto_20181015_1444"),
    ]

    operations = [
        migrations.AddField(
            model_name="casecontact",
            name="organisation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="organisations.Organisation",
            ),
        ),
        # migrations.RunPython(case_contact_org),
    ]
