from django.contrib.auth.models import Group

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, SubmissionType
from contacts.models import CaseContact, Contact
from core.models import User
from invitations.models import Invitation
from invitations.tests.test_invites import InviteTestBase, PASSWORD
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from security.models import UserCase


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

        third_party_invite_submission_type = SubmissionType.objects.get(
            pk=SUBMISSION_TYPE_INVITE_3RD_PARTY
        )
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
        self.assertFalse(
            CaseContact.objects.filter(
                case=self.case,
                contact=self.third_party_contact,
                organisation=self.third_party_organisation
            ).exists()
        )
        self.invitation.process_invitation(
            self.third_party_user,
            self.invitation.code,
            self.case.pk
        )
        self.assertTrue(
            CaseContact.objects.filter(
                case=self.case,
                contact=self.third_party_contact,
                organisation=self.organisation
            ).exists()
        )

    def test_user_case_created(self):
        """Tests that a new UserCase object is created, linking the third party organisation
        and the case.
        """
        self.assertFalse(
            UserCase.objects.filter(
                user=self.third_party_user,
                case=self.case,
                organisation=self.organisation
            ).exists()
        )
        self.invitation.process_invitation(
            self.third_party_user,
            self.invitation.code,
            self.case.pk
        )
        self.assertTrue(
            UserCase.objects.filter(
                user=self.third_party_user,
                case=self.case,
                organisation=self.organisation
            ).exists()
        )
