from django.test import TestCase

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY, SUBMISSION_TYPE_REGISTER_INTEREST
from cases.models import Submission, SubmissionType
from contacts.models import Contact
from core.models import User
from invitations.models import Invitation
from invitations.tests.test_invites import InviteTestBase, PASSWORD
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from security.models import OrganisationCaseRole
from django.contrib.auth.models import Group


class ThirdPartyInviteTest(InviteTestBase):
    fixtures = ["roles.json", "actions.json", "submission_document_types.json"]

    def setUp(self) -> None:
        super().setUp()
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        self.third_party_contact = Contact.objects.create(
            name="3rd Party Lawyer",
            email="3rd_party_lawyer@test.com"  # /PS-IGNORE
        )
        self.third_party_organisation = Organisation.objects.create(
            name="3rd Party Law Incorporated",
            companies_house_id="123456",
            address="Holborn",
            country="GB"
        )
        self.third_party_user = User.objects.create_user(
            name="3rd Party Lawyer",
            email="3rd_party_lawyer@test.com",  # /PS-IGNORE
            password=PASSWORD,
            contact=self.third_party_contact
        )

        third_party_invite_submission_type = SubmissionType.objects.get(pk=SUBMISSION_TYPE_INVITE_3RD_PARTY)
        self.third_party_invite_submission = Submission.objects.create(
            type=third_party_invite_submission_type,
            name="Invite 3rd party",
            case=self.case,
            contact=self.contact_1,
            created_by=self.user,
            organisation=self.organisation,
            received_from=self.user,
            organisation_name=self.organisation.name,
        )

        # Creating an invitation object to a NEW third party, i.e. self.user has invited a 3rd party
        # (self.third_party_contact) to join their case
        self.invitation = Invitation.objects.create(
            created_by=self.user,
            contact=self.third_party_contact,
            case=self.case,
            organisation=self.organisation,
            email=self.third_party_contact.email,
            submission=self.third_party_invite_submission
        )
        self.invitation.assign_organisation_user(
            user=self.third_party_user,
            organisation=self.third_party_organisation
        )
        self.invitation.create_codes()
        self.invitation.save()

    def test_invite_new_organisation(self):
        """Tests that when the third party is new and isn't associated with the case, they become so after their
        invite is processed.
        """
        self.assertFalse(OrganisationCaseRole.objects.has_organisation_case_role(
            organisation=self.third_party_organisation,
            case=self.case
        ))
        self.invitation.process_invitation(self.third_party_user, self.invitation.code, self.case.pk)
        self.assertTrue(OrganisationCaseRole.objects.has_organisation_case_role(
            organisation=self.third_party_organisation,
            case=self.case
        ))

    def test_registration_of_interest_created(self):
        """Tests that when the third party is new and isn't associated with the case, a draft registration of interest
        is created.
        """
        submission_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_REGISTER_INTEREST)
        self.assertFalse(Submission.objects.filter(
            type=submission_type,
            organisation=self.third_party_organisation,
            contact=self.third_party_contact,
            case=self.case
        ).exists())
        self.invitation.process_invitation(self.third_party_user, self.invitation.code, self.case.pk)

        submission = Submission.objects.filter(
            type=submission_type,
            organisation=self.third_party_organisation,
            contact=self.third_party_contact,
            case=self.case
        )
        self.assertTrue(submission.exists())
        self.assertTrue(submission.first().status.draft)

    def test_multiple_registration_interest_not_created(self):
        """Tests that when the third party is not new and is already associated with a case,
        a draft registration of interest is not created
        """
        self.invitation.process_invitation(self.third_party_user, self.invitation.code, self.case.pk)

        submission_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_REGISTER_INTEREST)
        submission_query_kwargs = {
            "type": submission_type,
            "organisation": self.third_party_organisation,
            "contact": self.third_party_contact,
            "case": self.case
        }

        self.assertEqual(Submission.objects.filter(**submission_query_kwargs).count(), 1)
        self.invitation.process_invitation(self.third_party_user, self.invitation.code, self.case.pk)
        self.assertEqual(Submission.objects.filter(**submission_query_kwargs).count(), 1)

    def test_organisation_case_role_not_approved(self):
        """Tests that the OrganisationCaseRole assigned to the third party organisation is not approved"""
        self.invitation.process_invitation(self.third_party_user, self.invitation.code, self.case.pk)
        self.assertTrue(OrganisationCaseRole.objects.get_organisation_role(
            self.case, self.third_party_organisation, outer=True
        ).approved_by is None)
