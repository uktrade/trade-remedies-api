from cases.models import Case
from config.test_bases import CaseSetupTestMixin
from organisations.models import Organisation
from organisations.services.v2.serializers import (
    DuplicateOrganisationMergeSerializer,
    OrganisationMergeRecordSerializer,
)


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


class TestMergeBase(CaseSetupTestMixin):
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
        self.organisation_object_2 = Organisation.objects.create(
            name="Fake Company LTD",
        )
        self.organisation_object_3 = Organisation.objects.create(
            name="COMPANY",
            address="Fake Address",
        )
        self.merge_record = self.organisation_object.find_potential_duplicate_orgs()


class TestMergeSerializers(TestMergeBase):
    def test_get_order_in_parent(self):
        serializer = DuplicateOrganisationMergeSerializer(
            self.merge_record.potential_duplicates().first()
        )
        assert serializer.data["order_in_parent"] == (0, 2)

    def test_identical_fields(self):
        serializer = DuplicateOrganisationMergeSerializer(
            self.merge_record.potential_duplicates().first()
        )
        assert serializer.data["identical_fields"] == ["name"]

        serializer = DuplicateOrganisationMergeSerializer(
            self.merge_record.potential_duplicates().last()
        )
        assert serializer.data["identical_fields"] == ["address"]


class TestOrganisationMergeRecordSerializer(TestMergeBase):
    def test_potential_duplicates(self):
        serializer = OrganisationMergeRecordSerializer(self.merge_record)
        assert (
            serializer.data["potential_duplicates"][0]
            == DuplicateOrganisationMergeSerializer(self.merge_record, many=True).data
        )

    def test_chosen_case_roles(self):
        serializer = OrganisationMergeRecordSerializer(
            self.merge_record,
            data={
                "chosen_case_roles_delimited": [
                    f"{self.contributor_case_role.id}*-*{self.case_object.id}"
                ]
            },
        )
        serializer.is_valid()
        serializer.save()
        self.merge_record.refresh_from_db()
        assert (
            self.merge_record.chosen_case_roles[self.case_object.id]
            == self.contributor_case_role.id
        )

        # now we test appending
        case_object_2 = Case.objects.create(
            name="test case",
            type=self.case_type_object,
        )
        serializer = OrganisationMergeRecordSerializer(
            self.merge_record,
            data={
                "chosen_case_roles_delimited": [
                    f"{self.applicant_case_role.id}*-*{case_object_2.id}"
                ]
            },
        )
        serializer.is_valid()
        serializer.save()

        self.merge_record.refresh_from_db()
        assert self.merge_record.chosen_case_roles[case_object_2.id] == self.applicant_case_role.id


class TestOrganisationMergeRecordModel(TestMergeBase):
    def test_potential_duplicates_order(self):
        assert (
            self.merge_record.potential_duplicates().first().child_organisation
            == self.organisation_object
        )
        assert (
            self.merge_record.potential_duplicates().last().child_organisation
            == self.organisation_object_3
        )
