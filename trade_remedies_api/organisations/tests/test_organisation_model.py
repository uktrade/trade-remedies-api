from django.utils import timezone

from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST
from cases.models import Submission
from config.test_bases import CaseSetupTestMixin
from contacts.models import CaseContact, Contact
from invitations.models import Invitation
from organisations.models import Organisation
from security.models import OrganisationCaseRole


class TestOrganisationRepresentativeCases(CaseSetupTestMixin):
    """Tests the representative_cases() method on the Organisation model."""

    def setUp(self) -> None:
        super().setUp()
        representative_cases = self.organisation.representative_cases()
        assert len(representative_cases) == 0
        self.now = timezone.now()

        # first we create say that self.organisation is representing Org B on the case
        org_b = Organisation.objects.create(name="Org B")
        self.org_b = org_b
        Contact.objects.create(
            name="org b contact",
            email="org_b_contact@example.com",  # /PS-IGNORE
            organisation=org_b,
        )

        self.contact_object.organisation = self.organisation
        self.contact_object.save()

        # associating org b with the case
        OrganisationCaseRole.objects.create(
            case=self.case_object,
            organisation=org_b,
            role=self.applicant_case_role,
            validated_at=self.now,
        )

        # now we say that the contact for self.organisation is representing org b on the case
        CaseContact.objects.create(
            contact=self.contact_object, case=self.case_object, organisation=org_b
        )

    def test_representative_cases_through_invitation(self):
        # invite was achieved using a representative invitation
        Invitation.objects.create(
            contact=self.contact_object,
            case=self.case_object,
            organisation=self.org_b,
            invitation_type=2,
            approved_at=self.now,
        )

        representative_cases = self.organisation.representative_cases()
        assert len(representative_cases) == 1
        assert representative_cases[0]["case"]["id"] == str(self.case_object.id)
        assert representative_cases[0]["on_behalf_of"] == self.org_b.name
        assert representative_cases[0]["role"] == self.applicant_case_role.name
        assert representative_cases[0]["validated"]
        assert representative_cases[0]["validated_at"] == self.now

    def test_representative_cases_through_roi(self):
        # invite was achieved using a ROI on behalf of org b
        Submission.objects.create(
            type_id=SUBMISSION_TYPE_REGISTER_INTEREST,
            contact=self.contact_object,
            case=self.case_object,
            organisation=self.org_b,
        )

        representative_cases = self.organisation.representative_cases()
        assert len(representative_cases) == 1
        assert representative_cases[0]["case"]["id"] == str(self.case_object.id)
        assert representative_cases[0]["on_behalf_of"] == self.org_b.name
        assert representative_cases[0]["role"] == self.applicant_case_role.name
        assert representative_cases[0]["validated"]
        assert representative_cases[0]["validated_at"] == self.now
