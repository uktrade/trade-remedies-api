from config.test_bases import CaseSetupTestMixin
from invitations.models import Invitation
from organisations.models import Organisation
from organisations.services.v2.serializers import (
    OrganisationCaseRoleSerializer,
    OrganisationSerializer,
)
from security.models import CaseRole, OrganisationCaseRole

from model_bakery import baker


class TestOrganisationFindPotentialDuplicates(CaseSetupTestMixin):
    def setUp(self) -> None:
        super().setUp()
        # creating the organisation that we will be testing against
        self.organisation_object = Organisation.objects.create(
            name="Fake Company LTD",
            address="Fake Address",
            postcode="12-34:2",
            companies_house_id="RepReg12345",
            organisation_website="www.example.com",
            vat_number="GB12 34 56 78",
            eori_number="GB123456789012",
            duns_number="111111111",
        )

    def test_no_matches(self):
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "no_duplicates_found"
        assert not merge_record.potential_duplicates()

    def test_name_match(self):
        # exact match required for name
        Organisation.objects.create(name="Fake Company LTD")
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "duplicates_found"
        assert merge_record.potential_duplicates()
        assert len(merge_record.potential_duplicates()) == 1

    def test_address_match(self):
        # exact match required for address
        Organisation.objects.create(address="Fake Address")
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "duplicates_found"
        assert merge_record.potential_duplicates()
        assert len(merge_record.potential_duplicates()) == 1

    def test_postcode_match(self):
        # fuzzy match required for postcode
        Organisation.objects.create(postcode="12342")
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "duplicates_found"
        assert merge_record.potential_duplicates()
        assert len(merge_record.potential_duplicates()) == 1

    def test_companies_house_id_match(self):
        # exact match required for companies_house_id
        Organisation.objects.create(companies_house_id="Rep Reg:12345")
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "duplicates_found"
        assert merge_record.potential_duplicates()
        assert len(merge_record.potential_duplicates()) == 1

    def test_organisation_website_match(self):
        # fuzzy match required for organisation_website
        Organisation.objects.create(organisation_website="https://www.cheese.example.com")
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "duplicates_found"
        assert merge_record.potential_duplicates()
        assert len(merge_record.potential_duplicates()) == 1

    def test_vat_number_match(self):
        # fuzzy match required for vat_number
        Organisation.objects.create(vat_number="12345678")
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "duplicates_found"
        assert merge_record.potential_duplicates()
        assert len(merge_record.potential_duplicates()) == 1

    def test_eori_number_match(self):
        # fuzzy match required for eori_number
        Organisation.objects.create(eori_number="GB12 34-5678-9012")
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "duplicates_found"
        assert merge_record.potential_duplicates()
        assert len(merge_record.potential_duplicates()) == 1

    def test_duns_number_match(self):
        # exact match required for duns_number
        Organisation.objects.create(duns_number="111111111")
        merge_record = self.organisation_object.find_potential_duplicate_orgs()
        assert merge_record.status == "duplicates_found"
        assert merge_record.potential_duplicates()
        assert len(merge_record.potential_duplicates()) == 1