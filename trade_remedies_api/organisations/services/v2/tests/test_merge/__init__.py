from config.test_bases import CaseSetupTestMixin
from organisations.models import Organisation


class MergeTestBase(CaseSetupTestMixin):
    """Base class for merge tests that create 3 duplicate organisations and a corresponding
    merge record.
    """

    def setUp(self):
        super().setUp()
        self.organisation_1 = Organisation.objects.create(
            name="Test Organisation 1",
            address="Test Address 1",
        )
        self.organisation_2 = Organisation.objects.create(
            name="Test Organisation 1",
            address="ADDY",
        )
        self.organisation_3 = Organisation.objects.create(
            name="Org 3",
            address="Test Address 1",
        )
        self.merge_record = self.organisation_1.find_potential_duplicate_orgs()
