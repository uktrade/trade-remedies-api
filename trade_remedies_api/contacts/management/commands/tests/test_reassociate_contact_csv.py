from importlib.resources import files
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact
from organisations.models import Organisation


class TestReAssociateContactCsv(TestCase):
    contact_id = "e9c8087c-6324-47d7-a355-3a0d5e23e9e0"
    organisation_name = "test company"
    csv_file = files("contacts.management.commands.tests") / "test.csv"

    def setUp(self) -> None:
        self.organisation_object = Organisation.objects.create(name=self.organisation_name)
        self.contact_object = Contact.objects.create(
            email="test@example.com", name="Test User", id=self.contact_id  # /PS-IGNORE
        )

    def call_command(self, dry_run=False):
        out = StringIO()
        call_command(
            "reassociate_contact_csv",
            file_path=self.csv_file,
            dry=dry_run,
            stdout=out,
            stderr=StringIO(),
        )
        return out.getvalue()

    def test_normal_operation(self):
        out = self.call_command()
        assert "Successfully associated 1 contacts" in out
        assert "Failed to associate 0 contacts" in out

        self.contact_object.refresh_from_db()
        assert self.contact_object.organisation.id == self.organisation_object.id

    def test_dry_run(self):
        out = self.call_command(dry_run=True)
        assert "Successfully associated 1 contacts" in out
        assert "Failed to associate 0 contacts" in out
        assert "Dry run, rolling back" in out

        self.contact_object.refresh_from_db()
        assert not self.contact_object.organisation

    def test_contact_already_associated(self):
        self.contact_object.organisation = Organisation.objects.create(name="another company")
        self.contact_object.save()

        out = self.call_command()
        assert "Successfully associated 0 contacts" in out
        assert "Failed to associate 1 contacts" in out

        self.contact_object.refresh_from_db()
        assert self.contact_object.organisation.id != self.organisation_object.id

    def test_multiple_organisations(self):
        Organisation.objects.create(name="test company")
        out = self.call_command()
        assert "Successfully associated 0 contacts" in out
        assert "Failed to associate 1 contacts" in out

        self.contact_object.refresh_from_db()
        assert not self.contact_object.organisation
