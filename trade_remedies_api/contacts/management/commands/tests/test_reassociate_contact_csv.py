import csv
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact
from organisations.models import Organisation


class TestReassociateContactCsv(TestCase):
    csv_written = False

    def setUp(self) -> None:
        self.organisation_object = Organisation.objects.create(name="test company")
        self.contact_object = Contact.objects.create(
            email="test@example.com", name="Test User"  # /PS-IGNORE
        )
        if not self.csv_written:
            writer = csv.writer(self.open_file, delimiter="*")
            writer.writerow([self.contact_object.id, self.organisation_object.name])
            self.csv_written = True

    @classmethod
    def setUpClass(cls):
        cls.temp_file = tempfile.NamedTemporaryFile()
        cls.open_file = open(cls.temp_file.name, "w", newline="")

    @classmethod
    def tearDownClass(cls):
        cls.open_file.close()

    def call_command(self, dry_run=False):
        out = StringIO()
        call_command(
            "reassociate_contact_csv",
            file_path=self.temp_file.name,
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
