from django.core.management import BaseCommand

from contacts.models import Contact
from core.models import User
from cases.models import Case
from organisations.models import Organisation
from security.models import (
    OrganisationCaseRole,
    CaseRole,
    CaseAction,
    UserCase,
    OrganisationUser,
)
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from django.utils import timezone


class Command(BaseCommand):

    help = """Command to associate a Contact with an Organisation. Some are missing this association
           as they were created either by mistake or a long time ago"""

    def add_arguments(self, parser):
        parser.add_argument("contact_id", nargs="+", type=str, help="Contact ID")
        parser.add_argument("organisation_id", nargs="+", type=str, help="Organisation ID")

    def handle(self, *args, **options):
        contact_object = Contact.objects.get(pk=options["contact_id"][0])
        organisation_object = Organisation.objects.get(pk=options["organisation_id"][0])

        contact_object.organisation = organisation_object
        contact_object.save()

        self.stdout.write(
            f"Contact {contact_object.email} has been assigned to {organisation_object.name}"
        )
