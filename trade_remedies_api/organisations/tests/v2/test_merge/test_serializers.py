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
    def test_pending_potential_duplicates(self):
        serializer = OrganisationMergeRecordSerializer(self.merge_record)
        assert "pending_potential_duplicates" in serializer.data
        assert len(serializer.data["pending_potential_duplicates"]) == 2

        self.merge_record.potential_duplicates().first().status = "confirmed_duplicate"
        self.merge_record.potential_duplicates().first().save()

        serializer = OrganisationMergeRecordSerializer(self.merge_record)
        assert len(serializer.data["pending_potential_duplicates"]) == 1

    def test_potential_duplicates(self):
        serializer = OrganisationMergeRecordSerializer(self.merge_record)
        assert (
            serializer.data["potential_duplicates"]
            == DuplicateOrganisationMergeSerializer(
                self.merge_record.potential_duplicates(), many=True
            ).data
        )

    def test_chosen_case_roles(self):
        serializer = OrganisationMergeRecordSerializer(
            instance=self.merge_record,
            data={
                "chosen_case_roles_delimited": f"{self.contributor_case_role.id}*-*{self.case_object.id}"
            },
            partial=True,
        )
        serializer.is_valid()
        serializer.save()
        self.merge_record.refresh_from_db()
        assert self.merge_record.chosen_case_roles[str(self.case_object.id)] == str(
            self.contributor_case_role.id
        )

        # now we test appending
        case_object_2 = Case.objects.create(
            name="test case",
            type=self.case_type_object,
        )
        serializer = OrganisationMergeRecordSerializer(
            instance=self.merge_record,
            data={
                "chosen_case_roles_delimited": f"{self.applicant_case_role.id}*-*{case_object_2.id}"
            },
            partial=True,
        )
        serializer.is_valid()
        serializer.save()

        self.merge_record.refresh_from_db()
        assert self.merge_record.chosen_case_roles[str(case_object_2.id)] == str(
            self.applicant_case_role.id
        )
