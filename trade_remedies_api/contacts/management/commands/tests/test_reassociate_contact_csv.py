import csv
import os
import uuid
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from contacts.models import Contact
from organisations.models import Organisation


class TestReassociateContactCsv(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.organisation_uuid = uuid.uuid4()
        cls.contact_uuid = uuid.uuid4()

        cls.organisation_object = Organisation.objects.create(
            name="test company", id=cls.organisation_uuid
        )
        cls.contact_object = Contact.objects.create(
            email="test@example.com", name="Test User", id=cls.contact_uuid  # /PS-IGNORE
        )
        cls.temp_file = tempfile.NamedTemporaryFile(delete=False)
        with open(cls.temp_file.name, "w", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter="*")
            writer.writerow([cls.contact_uuid, cls.organisation_uuid])

    @classmethod
    def tearDownClass(cls):
        Organisation.objects.get(id=cls.organisation_uuid).delete()
        Contact.objects.get(id=cls.contact_uuid).delete()
        os.remove(cls.temp_file.name)

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
