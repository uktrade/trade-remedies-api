import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def restore_contact_case_organisation(apps, schema_editor):
    from core.models import User
    from contacts.models import CaseContact

    users = User.objects.filter(userprofile__isnull=False)
    for user in users:
        contact = user.contact
        if user.organisation and user.contact.organisation != user.organisation.organisation:
            logger.info(
                f"Setting {user.organisation.organisation} against {contact} (formerly set to {contact.organisation})."
            )
            contact.organisation = user.organisation.organisation
            contact._disable_audit = True
            contact.save()
            case_contacts = CaseContact.objects.filter(contact=user.contact)
            for cc in case_contacts:
                logger.info(f"Got: {cc}")
                application_org = cc.case.application and cc.case.application.organisation
                if application_org:
                    try:
                        exists = CaseContact.objects.filter(
                            organisation=application_org, contact=cc.contact, case=cc.case
                        ).first()
                        if not exists:
                            logger.info(
                                f"Restoring {cc.contact} set as {cc.organisation or 'no org'} to {application_org} from the application for case {cc.case}"
                            )
                            cc.organisation = application_org
                            cc._disable_audit = True
                            logger.info("saving")
                            cc.save()
                    except Exception as exc:
                        logger.error(f"already set up: {exc}", exc_info=True)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_auto_20190227_1411"),
        ("contacts", "0004_auto_20190207_2037"),
    ]

    operations = [
        # migrations.RunPython(restore_contact_case_organisation),
    ]
