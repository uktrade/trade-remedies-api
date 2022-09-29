from django.contrib.auth.models import Group

from config.test_bases import OrganisationSetupTestMixin
from contacts.models import Contact
from core.models import User
from invitations.models import Invitation
from security.constants import SECURITY_GROUP_ORGANISATION_USER
from test_functional import FunctionalTestBase

new_name = "new name"
new_email = "new_email@example.com"  # /PS-IGNORE


class TestInvitationViewSet(OrganisationSetupTestMixin, FunctionalTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.invitation_object = Invitation.objects.create(
            organisation_security_group=Group.objects.get(name=SECURITY_GROUP_ORGANISATION_USER),
            name="test name",
            email="test@example.com",  # /PS-IGNORE
            organisation=self.organisation,
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
        self.assertFalse(self.invitation_object.sent_at)

        new_contact = Contact.objects.create(email=new_email, name=new_name)
        self.invitation_object.contact = new_contact
        self.invitation_object.created_by = self.user

        self.invitation_object.save()
        self.client.post(f"/api/v2/invitations/{self.invitation_object.pk}/send_invitation/")
        self.invitation_object.refresh_from_db()
        self.assertTrue(self.invitation_object.sent_at)

    def test_send_invitation_existing_user(self):
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

        self.assertFalse(User.objects.filter(email__iexact=new_email).exists)

        self.client.post(
            f"/api/v2/invitations/{self.invitation_object.pk}/create_user_from_invitation/"
        )

        user_query = User.objects.filter(email__iexact=new_email)
        self.assertTrue(user_query.exists)
        user_object = user_query.get()
        self.assertEqual(user_object.name, new_name)
        self.assertTrue(self.invitation_object.invited_user)
        self.assertEqual(self.invitation_object.invited_user, user_object)
