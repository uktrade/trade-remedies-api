from cases.models import Case
from organisations.services.v2.serializers import (
    DuplicateOrganisationMergeSerializer,
    OrganisationMergeRecordSerializer,
)
from organisations.tests.v2.test_merge import MergeTestBase


class TestDuplicateOrganisationMergeSerializer(MergeTestBase):
    def test_get_order_in_parent(self):
        serializer = DuplicateOrganisationMergeSerializer(
            self.merge_record.potential_duplicates().first()
        )
        assert serializer.data["order_in_parent"] == (0, 2)

    def test_identical_fields(self):
        serializer = DuplicateOrganisationMergeSerializer(
            self.merge_record.potential_duplicates().first()
        )
        assert serializer.data["identical_fields"] == ["address"]

        serializer = DuplicateOrganisationMergeSerializer(
            self.merge_record.potential_duplicates().last()
        )
        assert serializer.data["identical_fields"] == ["name"]


class TestOrganisationMergeRecordSerializer(MergeTestBase):
    def test_potential_duplicates(self):
        serializer = OrganisationMergeRecordSerializer(self.merge_record)
        assert (
            serializer.data["potential_duplicates"][0]
            == DuplicateOrganisationMergeSerializer(self.merge_record.potential_duplicates(), many=True).data
        )

    def test_chosen_case_roles(self):
        serializer = OrganisationMergeRecordSerializer(
            self.merge_record,
            data={
                "chosen_case_roles_delimited": f"{self.contributor_case_role.id}*-*{self.case_object.id}"

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
                "chosen_case_roles_delimited": f"{self.applicant_case_role.id}*-*{case_object_2.id}"
            },
        )
        serializer.is_valid()
        serializer.save()

        self.merge_record.refresh_from_db()
        assert self.merge_record.chosen_case_roles[case_object_2.id] == self.applicant_case_role.id
