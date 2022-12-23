from unittest.mock import patch

from django.contrib.auth.models import Group

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, get_submission_type
from config.test_bases import CaseSetupTestMixin
from contacts.models import CaseContact, Contact
from core.models import User
from invitations.models import Invitation
from organisations.models import Organisation
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from security.models import UserCase
from test_functional import FunctionalTestBase

new_name = "new name"
new_email = "new_email@example.com"  # /PS-IGNORE


class TestInvitationViewSet(CaseSetupTestMixin, FunctionalTestBase):
    def setUp(self) -> None:
        super().setUp()
        submission_type = get_submission_type(SUBMISSION_TYPE_INVITE_3RD_PARTY)
        submission_status = submission_type.default_status
        self.submission_object = Submission.objects.create(
            name="Invite 3rd party",
            type=submission_type,
            status=submission_status,
            case=self.case_object,
            contact=self.contact_object,
            organisation=self.organisation,
        )
        self.invitation_object = Invitation.objects.create(
            organisation_security_group=Group.objects.get(name=SECURITY_GROUP_ORGANISATION_USER),
            name="test name",
            email="test@example.com",  # /PS-IGNORE
            organisation=self.organisation,
            case=self.case_object,
            user=self.user,
            submission=self.submission_object,
            contact=self.contact_object,
        )

    def test_update_contact_creation(self):
        self.assertFalse(Contact.objects.filter(email=new_email, name=new_name).exists())

        self.client.put(
            f"/api/v2/invitations/{self.invitation_object.pk}/",
            data={
                "name": new_name,
                "email": new_email,
            },
        )

        self.assertTrue(Contact.objects.filter(email=new_email, name=new_name).exists())
        self.invitation_object.refresh_from_db()
        self.assertTrue(self.invitation_object.contact.name == new_name)
        self.assertTrue(self.invitation_object.contact.email == new_email)

    def test_update_contact_update(self):
        new_contact = Contact.objects.create(email=new_email, name=new_name)
        self.invitation_object.contact = new_contact
        self.invitation_object.save()

        invitation = self.client.put(
            f"/api/v2/invitations/{self.invitation_object.pk}/",
            data={
                "name": "new NEW name",
                "email": "new_new_email@example.com",  # /PS-IGNORE
            },
        )
        self.invitation_object.refresh_from_db()
        self.assertFalse(self.invitation_object.contact == new_contact)
        self.assertTrue(self.invitation_object.contact.name == "new NEW name")
        self.assertTrue(
            self.invitation_object.contact.email == "new_new_email@example.com"  # /PS-IGNORE
        )

    def test_send_invitation_new_user(self):
        self.invitation_object.invitation_type = 2
        self.invitation_object.save()
        self.assertFalse(self.invitation_object.sent_at)

        new_contact = Contact.objects.create(
            email=new_email, name=new_name, organisation=self.organisation
        )
        self.invitation_object.contact = new_contact
        self.invitation_object.created_by = self.user

        self.invitation_object.save()
        self.client.post(f"/api/v2/invitations/{self.invitation_object.pk}/send_invitation/")
        self.invitation_object.refresh_from_db()
        self.assertTrue(self.invitation_object.sent_at)

    def test_send_invitation_existing_user(self):
        self.invitation_object.invitation_type = 2
        self.invitation_object.save()
        self.assertFalse(self.invitation_object.sent_at)
        user = User.objects.create_new_user(
            name="test1",
            email="test1@example.com",  # /PS-IGNORE
        )
        new_contact = Contact.objects.create(
            email="test1@example.com",  # /PS-IGNORE
            name="test1",
            organisation=self.organisation,
        )
        self.invitation_object.contact = new_contact
        self.invitation_object.created_by = self.user

        self.invitation_object.save()
        self.client.post(f"/api/v2/invitations/{self.invitation_object.pk}/send_invitation/")
        self.invitation_object.refresh_from_db()
        self.assertEqual(self.invitation_object.invited_user, user)
        self.assertTrue(self.invitation_object.sent_at)

    def test_create_user_from_invitation(self):
        self.assertFalse(self.invitation_object.invited_user)
        new_contact = Contact.objects.create(email=new_email, name=new_name)
        self.invitation_object.contact = new_contact
        self.invitation_object.created_by = self.user
        self.invitation_object.save()

        self.assertFalse(User.objects.filter(email__iexact=new_email).exists())

        self.client.post(
            f"/api/v2/invitations/{self.invitation_object.pk}/create_user_from_invitation/"
        )

        user_query = User.objects.filter(email__iexact=new_email)
        self.assertTrue(user_query.exists())
        user_object = user_query.get()
        self.assertEqual(user_object.name, new_name)
        self.invitation_object.refresh_from_db()
        self.assertTrue(self.invitation_object.invited_user)
        self.assertEqual(self.invitation_object.invited_user, user_object)

    def approve_representative_invitation_org_assignment(self):
        self.invitation_object.invitation_type = 2
        self.invitation_object.save()

        assert not self.invitation_object.invited_user.is_member_of(
            self.invitation_object.organisation
        )
        self.client.patch(
            f"/api/v2/invitations/{self.invitation_object.pk}/process_representative_invitation/",
            data={"approved": "yes"},
        )
        self.invitation_object.invited_user.refresh_from_db()
        assert self.invitation_object.invited_user.is_member_of(self.invitation_object.organisation)

    def test_approve_representative_invitation_case_assignment(self):
        self.invitation_object.invitation_type = 2
        invited_org = Organisation.objects.create(name="invited organisation")
        new_contact = Contact.objects.create(
            email=new_email, name=new_name, organisation=invited_org
        )
        self.invitation_object.created_by = self.user
        self.invitation_object.contact = new_contact
        self.invitation_object.save()

        self.client.post(
            f"/api/v2/invitations/{self.invitation_object.pk}/create_user_from_invitation/"
        )

        user_case_object = UserCase.objects.create(
            user=self.user, case=self.case_object, organisation=self.organisation
        )
        self.invitation_object.user_cases_to_link.add(user_case_object)

        self.invitation_object.refresh_from_db()
        assert not UserCase.objects.filter(
            user=self.invitation_object.invited_user,
            case=self.case_object,
            organisation=self.organisation,
        ).exists()
        assert not CaseContact.objects.filter(
            contact=self.invitation_object.contact,
            case=self.case_object,
            organisation=self.organisation,
        ).exists()

        assert not self.invitation_object.submission.status.review_ok
        self.invitation_object.invited_user.is_active = True
        self.invitation_object.invited_user.save()
        self.client.patch(
            f"/api/v2/invitations/{self.invitation_object.pk}/process_representative_invitation/",
            data={"approved": "yes"},
        )
        assert UserCase.objects.filter(
            user=self.invitation_object.invited_user,
            case=self.case_object,
            organisation=self.organisation,
        ).exists()
        assert CaseContact.objects.filter(
            contact=self.invitation_object.contact,
            case=self.case_object,
            organisation=self.organisation,
        ).exists()

        self.invitation_object.submission.refresh_from_db()
        assert self.invitation_object.submission.status.review_ok

    @patch("core.tasks.send_mail")
    def test_process_representative_invite_email_chocie(self, send_mail):
        self.invitation_object.invitation_type = 2
        self.invitation_object.save()
        new_contact = Contact.objects.create(
            email=new_email, name=new_name, organisation=self.organisation
        )
        self.invitation_object.contact = new_contact
        self.invitation_object.created_by = self.user
        self.invitation_object.save()

        self.client.post(
            f"/api/v2/invitations/{self.invitation_object.pk}/create_user_from_invitation/"
        )

        self.client.patch(
            f"/api/v2/invitations/{self.invitation_object.pk}/process_representative_invitation/",
            data={"approved": "yes"},
        )

        # assert send_mail.called_with

    def test_caseworker_invite_existing_contact(self):
        # tests that the caseworker invite creation reuses existing contacts
        org = Organisation.objects.create(
            name="duplicate org",
            draft=True,
        )
        duplicate_contact = Contact.objects.create(
            organisation=org,
            name=self.contact_object.name,
            email=self.contact_object.email,
        )

        # the viewset should now pickup on the fact that the email already belongs to a
        response = self.client.post(
            "/api/v2/invitations/",
            data={
                "organisation": org.id,
                "case": self.case_object.id,
                "contact": duplicate_contact.id,
                "invitation_type": 3,
                "name": self.contact_object.name,
                "email": self.contact_object.email,
                "case_role_key": "applicant",
            },
        )

        new_invitation = response.json()
        assert new_invitation["contact"]["id"] != str(duplicate_contact.id)
        assert new_invitation["contact"]["id"] == str(self.contact_object.id)

        # now checking the org has been deleted
        org.refresh_from_db()
        assert org.deleted_at

    def test_caseworker_invite_new_contact_used(self):
        # tests that the caseworker invite creation reuses existing contacts
        org = Organisation.objects.create(name="duplicate org")
        duplicate_contact = Contact.objects.create(
            organisation=org,
            name="new contact name",
            email="newemail@example.com",  # /PS-IGNORE
        )

        # the viewset should now pickup on the fact that the email already belongs to a
        response = self.client.post(
            "/api/v2/invitations/",
            data={
                "organisation": org.id,
                "case": self.case_object.id,
                "contact": duplicate_contact.id,
                "invitation_type": 3,
                "name": self.contact_object.name,
                "email": self.contact_object.email,
                "case_role_key": "applicant",
            },
        )

        new_invitation = response.json()
        assert new_invitation["contact"]["id"] == str(duplicate_contact.id)
        assert new_invitation["contact"]["id"] != str(self.contact_object.id)

    def test_send_representative_invitation_existing_user(self):
        """tests that when an existing user is sent a rep invite, the submission is marked as
        received and the invitation as accepted
        """
        assert not self.invitation_object.submission.status.received
        assert not self.invitation_object.accepted_at
        assert not self.invitation_object.invited_user
        self.client.post(f"/api/v2/invitations/{self.invitation_object.pk}/send_invitation/")
        self.invitation_object.refresh_from_db()
        assert self.invitation_object.submission.status.received
        assert self.invitation_object.accepted_at
        assert self.invitation_object.invited_user == self.user

    def test_send_representative_invitation_existing_user(self):
        """tests that when an existing user is sent a rep invite, the submission is marked as
        received and the invitation as accepted
        """
        new_contact = Contact.objects.create(email=new_email, name=new_name)
        self.invitation_object.contact = new_contact
        self.invitation_object.save()

        assert not self.invitation_object.submission.status.sent

        self.client.post(f"/api/v2/invitations/{self.invitation_object.pk}/send_invitation/")
        self.invitation_object.refresh_from_db()
        assert self.invitation_object.submission.status.sent
        assert not self.invitation_object.accepted_at
