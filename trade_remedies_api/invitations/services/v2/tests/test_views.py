from django.contrib.auth.models import Group

from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY
from cases.models import Submission, get_submission_type
from config.test_bases import CaseSetupTestMixin, OrganisationSetupTestMixin
from contacts.models import Contact
from core.models import User
from invitations.models import Invitation
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

        invitation = self.client.put(
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
                "email": "new_NEW_email@example.com",  # /PS-IGNORE
            },
        )
        self.invitation_object.refresh_from_db()
        self.assertFalse(self.invitation_object.contact == new_contact)
        self.assertTrue(self.invitation_object.contact.name == "new NEW name")
        self.assertTrue(
            self.invitation_object.contact.email == "new_NEW_email@example.com"  # /PS-IGNORE
        )

    def test_send_invitation_new_user(self):
        self.invitation_object.invitation_type = 2
        self.invitation_object.save()
        self.assertFalse(self.invitation_object.sent_at)

        new_contact = Contact.objects.create(email=new_email, name=new_name)
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
        new_contact = Contact.objects.create(email="test1@example.com", name="test1")  # /PS-IGNORE
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

    def test_user_cases_to_link_deleted(self):
        """Checks that user_cases_to_link is cleared when we perform an update and choose later"""
        user_case_object = UserCase.objects.create(
            user=self.user,
            case=self.case_object,
            organisation=self.organisation
        )
        self.invitation_object.user_cases_to_link.add(user_case_object)
        assert user_case_object in self.invitation_object.user_cases_to_link.all()
        self.client.put(
            f"/api/v2/invitations/{self.invitation_object.pk}/",
            data={
                "name": "new NEW name",
                "user_cases_to_link": "choose_user_case_later"
            },
        )
        self.invitation_object.refresh_from_db()
        assert user_case_object not in self.invitation_object.user_cases_to_link.all()

