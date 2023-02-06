from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact
from organisations.models import Organisation


class TestReassociateContactOrg(TestCase):
    def test_command(self):
        contact_object = Contact.objects.create(name="test", email="test@example.com")  # /PS-IGNORE
        organisation_object = Organisation.objects.create(name="test company")
        assert not contact_object.organisation
        call_command(
            "reassociate_contact_org",
            contact_object.id,
            organisation_object.id
        )
        contact_object.refresh_from_db()
        assert contact_object.organisation == organisation_object
