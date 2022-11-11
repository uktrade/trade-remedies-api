import uuid

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models, transaction
from django.utils import crypto, timezone

from audit import AUDIT_TYPE_EVENT, AUDIT_TYPE_NOTIFY
from audit.utils import audit_log
from cases.constants import SUBMISSION_TYPE_INVITE_3RD_PARTY, SUBMISSION_TYPE_REGISTER_INTEREST
from cases.models import Case, Submission, SubmissionType
from contacts.models import CaseContact, Contact
from core.base import BaseModel
from core.models import SystemParameter, User
from core.notifier import notify_contact_email, notify_footer
from core.tasks import send_mail
from core.utils import convert_to_e164
from organisations.models import Organisation, get_organisation
from security.constants import (
    ROLE_AWAITING_APPROVAL,
    ROLE_PREPARING,
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_THIRD_PARTY_USER,
)
from security.models import CaseRole, OrganisationCaseRole, UserCase
from .exceptions import InvitationFailure, InviteAlreadyAccepted


class InvitationManager(models.Manager):
    def _validate_invitation(self, organisation, email, user_id=None):
        """
        Validate an invitation exists for this email address.
        If a user_id is provided it is used to more precisely find the invited user
        """
        organisation = get_organisation(organisation)
        invitation = self.filter(email=email.strip(), organisation=organisation)
        if user_id:
            invitation = invitation.filter(user_id=user_id)
        if invitation:
            return invitation.first()
        else:
            return False

    def get_invite_by_code(self, invitation_code):
        """
        Validate an invitation exists for user/code/case combination.
        """
        invitation = self.select_related(
            "submission", "submission__organisation", "organisation", "contact"
        ).filter(code=invitation_code, deleted_at__isnull=True, accepted_at__isnull=True)

        invitation = invitation.first()
        return invitation

    def validate_all_pending(self, user, invitation_code=None):
        """
        validate all pending invitations for a user.
        If invitation code is provided, prepare (process) that invitation beforehand.
        """
        accepted = []
        pending_invites_for_user = self.filter(
            invited_user=user, accepted_at__isnull=True, deleted_at__isnull=True
        )
        for invitation in pending_invites_for_user:
            invitation.accept_invitation()
        if invitation_code:
            invitation = self.get_invite_by_code(invitation_code)
            if invitation and invitation.email == user.email:
                # We only want to process the invitation if it belongs to the user logging in
                invitation.process_invitation(user, accept=True, register_interest=True)
        pending_invites = self.filter(user=user, accepted_at__isnull=True, deleted_at__isnull=True)
        for invite in pending_invites:
            invite.accepted()
            accepted.append(invite.id)
        return accepted

    def validate_public_invite(self, short_code, user):
        """
        Validate a public invite not issued to a specific organisation,
        but to the general public via
        a code. Members of this invite will by default go to the awaiting approval group and
        will not have access to the case while in that group.
        Returns a tuple of the invite model and the organisation used.
        Raises an InvitationFailure if the code is not found
        """
        try:

            invite = self.get(short_code=short_code, deleted_at__isnull=True)
            organisation_user = invite.process_invitation(user=user, accept=False)
            organisation = organisation_user.organisation
            audit_log(
                audit_type=AUDIT_TYPE_EVENT,
                user=user,
                case=self.case,
                data={
                    "invite_id": str(invite.id),
                    "accepted_by": str(user.id),
                    "organisation_id": str(organisation.id),
                },
            )
            return invite
        except Invitation.DoesNotExist:
            raise InvitationFailure(f"Invalid short code: {short_code}")

    @transaction.atomic
    def create_user_invite(self, user_email, organisation, invited_by, meta):
        """
        Create an invite for a user to join an organisation as a direct employee.
        The invite's meta data contains all the parameters required to create the user
        record once the user accepts the invite.
        A contact record will be created for this user, which will later be re-assigned
        to the user upon completing registration. Note that at this stage the organisation is NOT
        set against the contact, to prevent it appearing until the user accepts. Then the org
        assignment is made.
        If an invite is already present and not responded to it will be refreshed.

        :param (str) user_email: The user to be invited.
        :param (Organisation) organisation: The organisation invited to
        :param (User) invited_by: The user creating the invitation.
        :param (dict) meta: invite meta data.
        """
        created = True
        user_email = user_email.lower()
        try:
            invite = Invitation.objects.get(
                organisation=organisation, email=user_email, deleted_at__isnull=True
            )
            created = False
        except Invitation.DoesNotExist:
            invite = Invitation.objects.create(
                organisation=organisation,
                email=user_email,
                user_context=invited_by,
            )
        if invite.accepted_at:
            raise InviteAlreadyAccepted(
                f"The user {user_email} has already been invited to {organisation} "
                "and has accepted the invite."
            )
        if (
            not created
            and (timezone.now() - invite.created_at).seconds / 3600
            > settings.ORGANISATION_INVITE_DURATION_HOURS
        ):
            invite = invite.recreate()
        invite.created_by = invited_by
        invite.create_codes()
        if meta and meta.get("email"):
            meta["email"] = meta["email"].lower()
        invite.meta = meta
        phone = convert_to_e164(meta.get("phone")) if meta.get("phone") else None
        invite.contact = Contact.objects.create_contact(
            created_by=invited_by,
            name=meta["name"],
            email=user_email,
            phone=phone,
            country=meta.get("country"),
        )
        invite.save()
        invite.send(
            sent_by=invited_by,
            direct=False,
            template_key="NOTIFY_INVITE_ORGANISATION_USER",
            context={
                "login_url": f"{settings.PUBLIC_ROOT_URL}/invitation/{invite.code}/for/{organisation.id}/"
                # noqa: E501
            },
        )
        return invite

    @transaction.atomic
    def invite_existing_user(self, user, organisation, invited_by, name=None, meta=None):
        """Create an invitation for an existing user.
        The invite is accepted, but marked invalid at the start
        in order to mask the fact the user already exists.

        Arguments:
            user {User} -- The user being invited
            organisation {Organisation} -- The organisation inviting the user
            invited_by {User} -- The user making the invite

        Keyword Arguments:
            name {str} -- The name specified by the inviter (default: {None})

        Returns:
            Invite -- Returns an invite model
        """
        existing = Invitation.objects.filter(
            user=user, organisation=organisation, deleted_at__isnull=True
        )
        if existing and len(existing) == 1:
            invite, created = existing[0], False
        elif (existing and len(existing) > 1) or not existing:
            for invite in existing:
                invite.delete()
            invite, created = Invitation.objects.get_or_create(
                user=user, organisation=organisation, deleted_at__isnull=True
            )
        invite.created_by = invited_by
        invite.contact = user.contact
        invite.email = user.email
        invite.name = name
        invite.invalid = True
        if meta:
            invite.meta = meta
        invite.save()
        invite.send(
            sent_by=invited_by,
            direct=False,
            template_key="NOTIFY_INVITE_EXISTING_ORGANISATION_USER",
        )
        return invite

    @staticmethod
    def get_user_invite(invite_id, requested_by):
        """Return a user invite model by id, if the requested_by user is allowed to see it.

        Arguments:
            invite_id {str} -- Invite UUID
            requested_by {User} -- The user requesting the invite data

        Returns:
            {Invitation} -- Invitation model
        """
        invite = Invitation.objects.get(id=invite_id, deleted_at__isnull=True)
        if (
            requested_by.is_tra()
            or invite.created_by.organisation.organisation == requested_by.organisation.organisation
        ):
            return invite
        return None


class Invitation(BaseModel):
    """
    An invitation can be made by a TRA user or an organisation owner user. The latter would also be
    bound to an invite submission used to facilitate the invite.
    An invitation can also be made by an organisation owner to invite a user to their organisation
    as a direct employee.
    In this scenario the user is already created and associated with the invite
    and will confirm the account details, set a password etc. via a special login link.
    These direct invites are not associated with a specific case.

    An invitation can be marked invalid which can happen
    if for example an existing public user is invited.
    A record of the invite still exists,
    but the user exercise it. Any temporary/permanent meta-data
    related to the invite can be saved in the meta dict.
    """

    invitation_type_choices = (
        (1, "Own Organisation"),
        (2, "Representative"),
        (3, "Caseworker"),
    )

    organisation = models.ForeignKey(
        "organisations.Organisation", null=True, blank=True, on_delete=models.PROTECT
    )
    organisation_security_group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.PROTECT
    )
    contact = models.ForeignKey("contacts.Contact", null=True, blank=True, on_delete=models.PROTECT)
    case = models.ForeignKey("cases.Case", null=True, blank=True, on_delete=models.PROTECT)
    submission = models.ForeignKey(
        "cases.Submission",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invitations",
    )
    case_role = models.ForeignKey(
        "security.CaseRole", null=True, blank=True, on_delete=models.PROTECT
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT
    )
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invited_user",
    )
    name = models.CharField(max_length=250, null=True, blank=True)
    email = models.EmailField(null=False, blank=True)
    invalid = models.BooleanField(default=False)
    code = models.CharField(max_length=50, null=True, blank=True, unique=True)
    short_code = models.CharField(max_length=16, null=True, blank=True, unique=True)
    email_sent = models.BooleanField(null=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approved",
    )
    meta = models.JSONField(default=dict)

    draft = models.BooleanField(default=False)
    invitation_type = models.PositiveIntegerField(
        null=True, blank=True, choices=invitation_type_choices
    )
    cases_to_link = models.ManyToManyField(Case, related_name="cases_to_link", blank=True)
    user_cases_to_link = models.ManyToManyField(
        UserCase, related_name="user_cases_to_link", blank=True
    )

    objects = InvitationManager()

    def __str__(self):
        return f"{self.organisation} invites {self.contact}"

    def save(self, *args, **kwargs):
        if not self.short_code or not self.code:
            self.create_codes()
        super().save(*args, **kwargs)

    def _to_dict(self):
        _dict = {
            "organisation": self.organisation.to_embedded_dict() if self.organisation else None,
            "organisation_security_group": self.organisation_security_group.name
            if self.organisation_security_group
            else None,
            "contact": self.contact.to_dict() if self.contact else None,
            "country_code": self.contact.country.code
            if self.contact and self.contact.country
            else "GB",
            "email": self.contact.email if self.contact else None,
            "user": self.user.to_embedded_dict() if self.user else None,
            "code": self.code,
            "short_code": self.short_code,
            "invalid": self.invalid,
            "submission": None,
            "case": {},
            "email_sent": self.email_sent,
            "accepted_at": self.accepted_at.strftime(settings.API_DATETIME_FORMAT)
            if self.accepted_at
            else None,
            "sent_at": self.sent_at.strftime(settings.API_DATETIME_FORMAT)
            if self.sent_at
            else None,
            "approved_by": self.approved_by.to_embedded_dict() if self.approved_by else None,
            "meta": self.meta,
        }
        if self.submission:
            _dict["submission"] = {
                "id": str(self.submission.id),
                "name": self.submission.name,
            }
        if self.case:
            _dict["case"] = {
                "id": str(self.case.id),
                "name": self.case.name,
                "reference": self.case.reference,
            }
        return _dict

    def recreate(self):
        """
        Delete this invite and recreate/refresh it
        """
        self.delete()
        self.id = None
        self.created_at = timezone.now()
        self.create_codes()
        self.save()
        return self

    def create_codes(self):
        self.short_code = crypto.get_random_string(8)
        self.code = str(uuid.uuid4())

    def send(self, sent_by, context=None, direct=False, template_key=None, footer_case_email=True):
        """Send the invite email via notify

        Arguments:
            sent_by {User} -- The user sending the invitation

        Keyword Arguments:
            context {dict} -- extra context dict (default: {None})
            direct {bool} -- include a direct login link with the invite codes (default: {False})
            template_key {str} -- The system param pointing to the template id (default: {None})
            no_case_email {str} -- True you want to include the case email in the footer (default: {True})

        Raises:
            InvitationFailure: raises if the invite is lacking a contact reference
        """
        if not self.contact:
            raise InvitationFailure("No contact to invite")
        template_key = template_key or "NOTIFY_INFORM_INTERESTED_PARTIES"
        notify_template_id = SystemParameter.get(template_key)
        _context = {
            "organisation_name": self.organisation.name,
            "company_name": self.organisation.name,
            "full_name": self.contact.name,  # invited contact
            "login_url": f"{settings.PUBLIC_ROOT_URL}",
            "guidance_url": SystemParameter.get("LINK_HELP_BOX_GUIDANCE"),
            "invited_by": self.created_by.name,
        }
        if self.case:
            product = self.case.product_set.first()
            export_source = self.case.exportsource_set.first()
            case_name = self.case.name or (product.sector.name if product else "N/A")
            _context.update(
                {
                    "case_name": case_name,
                    "case_number": self.case.reference,
                    "investigation_type": self.case.type.name,
                    "dumped_or_subsidised": self.case.dumped_or_subsidised(),
                    "product": product.name,
                    "country": export_source.country.name if export_source else None,
                    "notice_url": self.submission.url if self.submission else "",  # TODO: Remove
                    "notice_of_initiation_url": self.case.latest_notice_of_initiation_url,
                    "invited_by_name": self.submission.contact.name if self.submission else "",
                    "invited_by_organisation": self.submission.organisation.name
                    if self.submission
                    else "",
                }
            )
        # Set email and footer appropriate to case context
        email = notify_contact_email(_context.get("case_number"))
        _context.update({"email": email})
        if footer_case_email:
            _context.update({"footer": notify_footer(email)})
        if direct is True:
            _context[
                "login_url"
            ] = f"{settings.PUBLIC_ROOT_URL}/invitation/{self.code}/{self.case.id}/"
        if context:
            _context.update(context)

        audit_kwargs = {
            "audit_type": AUDIT_TYPE_NOTIFY,
            "user": sent_by,
            "case": self.case,
            "model": self.contact,
        }
        send_mail(self.contact.email, _context, notify_template_id, audit_kwargs=audit_kwargs)
        self.sent_at = timezone.now()
        self.email_sent = True
        self.save()

    def accepted(self):
        """
        Accept an invitation, logging the acceptance date/time (utc)
        """
        self.accepted_at = timezone.now()
        self.save()

    def assign_case_user(self, user=None, organisation=None):
        """
        Assign the user to the case
        """
        user = user or self.user
        organisation = organisation or self.organisation
        assigned = False
        if user:
            assigned = self.case.assign_organisation_user(user, organisation)
        return assigned

    def assign_organisation_user(self, user=None, organisation=None):
        """Assign Organisation User.

        Assign the user (or the invitation user) to the invitation organisation.
        If an owner exists already for this organisation, use the USER group,
        Otherwise the user becomes the new owner of this organisation.

        :param (User) user: User to add.
        :param (Organisation) organisation: Organisation for user.
        """
        user = user or self.user
        organisation = organisation or self.organisation
        existing_owner = organisation.get_owner()
        group = (
            SECURITY_GROUP_ORGANISATION_OWNER
            if not existing_owner
            else SECURITY_GROUP_ORGANISATION_USER
        )
        return organisation.assign_user(user, group)

    def create_registration_of_interest(
        self, user: User, organisation: Organisation, **kwargs
    ) -> Submission:
        """
        Creates and returns a new registration of interest.

        Arguments:
            user: A User object
            organisation: an Organisation object
            submission_type: a SubmissionType object, defaults to SUBMISSION_TYPE_REGISTER_INTEREST if not provided
            **kwargs: any value you provide in this dictionary will get passed to the Submission object and take
            precedence over defaults
        Returns:
            Submission object
        """

        submission_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_REGISTER_INTEREST)
        submission_kwargs = {
            "created_by": user,
            "organisation": organisation,
            "type": submission_type,
            "name": submission_type.name,
            "status": submission_type.default_status,
            "case": self.case,
            "contact": user.contact,
            "user_context": user,
        }
        submission_kwargs = {**submission_kwargs, **kwargs}
        new_registration_of_interest = Submission(**submission_kwargs)
        new_registration_of_interest.save()
        return new_registration_of_interest

    @transaction.atomic  # noqa:C901
    def process_invitation(
        self,
        user: User,
        accept: bool = False,
        organisation: Organisation = None,
        assign_to_organisation: bool = False,
        register_interest: bool = False,
        newly_registered: bool = False,
    ):
        """
        Process an invitation for a user. An invitation is usually generated by another user
        inviting this user to his view of the case (silo).
        The user will be added to the case under the inviting organisation.

        By default, the invitation is not accepted unless accept is True. This is
        done on first login where all pending invites are accepted.
        Generic invites, which are not tied to a specific user will not be updated
        with the invite details.

        By default, the user will not become a user of the organisation. This is only reserved for
        situations where the TRA are inviting a user they have added as a party themselves.

        If register_interest is True, a registration of interest will be created for this user
        for the case represented in the invite.

        If the user arrives without an organisation
        it will be because they have arrived via the invite flow and elected that they
        are the organisation invited. In this scenario the organisation invited will be their
        organisation.

        If the user already has an organisation, that differs from the one invited,
        a registration of interest will not be created.

        In the case where the invite originated from the caseworker, the organisation will
        be pre-approved to the case, thus retaining their role even as the user
        follows through the registration of interest
        (what would normally make them 'awaiting approval').

        The organisation will still require verification
        by the TRA before they are approved to the case.
        """
        from cases.models import Submission, SubmissionType
        from security.models import OrganisationCaseRole, CaseRole

        if self.submission:
            organisation = self.submission.organisation
        else:
            organisation = organisation or self.organisation
        # if a different organisation is associated with the user already,
        # update the invite meta data to reflect that.
        if user.organisation:
            self.meta.update(
                {
                    "accepted_as_organisation": {
                        "id": str(user.organisation.organisation.id),
                        "name": user.organisation.organisation.name,
                    },
                    "accepted_as_user": {
                        "id": str(user.id),
                        "name": user.name,
                        "email": user.email,
                    },
                    "accepted_as_contact": {
                        "id": str(user.contact.id),
                        "name": user.contact.name,
                    },
                }
            )
            if user.organisation.organisation != organisation:
                organisation = user.organisation.organisation
                register_interest = False

        # if a registration of interest is to be created, do it now.
        if register_interest:
            reg_interest = self.create_registration_of_interest(
                user=user, organisation=organisation
            )
            try:
                # retain the existing role of the organisation in the case, if available
                existing_case_role = OrganisationCaseRole.objects.get(
                    organisation=organisation, case=self.case
                )
                case_role = existing_case_role.role
            except OrganisationCaseRole.DoesNotExist:
                # otherwise set the draft to preparing,
                # falling back on the default process (preparing->awaiting)
                case_role = CaseRole.objects.get(id=ROLE_PREPARING)
            OrganisationCaseRole.objects.assign_organisation_case_role(
                organisation=organisation,
                case=self.case,
                role=case_role,
                sampled=True,
                created_by=user,
                approved_by=self.created_by,
                approved_at=self.created_at,
            )
            user.contact.set_primary(case=self.case, organisation=organisation, request_by=user)
            self.meta["created_submission_id"] = str(reg_interest.id)
            self.user = user
            assign_to_organisation = True
            assigned = True
            accept = True
        elif self.submission and self.submission.type.id == SUBMISSION_TYPE_INVITE_3RD_PARTY:
            assign_to_organisation = (
                True  # todo - maybe we don't need this if the user is already assigned
            )
            assigned = self.assign_case_user(user=user, organisation=self.organisation)
            accept = True  # We want the invitation to be accepted
            CaseContact.objects.get_or_create(
                case=self.case,
                contact=user.contact,
                organisation=self.organisation,
                primary=False,
            )
        else:
            assigned = self.assign_case_user(user=user, organisation=organisation)
        if assign_to_organisation:
            if not newly_registered:
                # If the user has just been newly registered as part of the RegistrationAPIView, then they have been
                # assigned to the organisation already, we don't want to overwrite it here as it will cause the
                # created OrganisationUser object to be an Organisation Member when in reality they should be a owner
                self.assign_organisation_user(user=user, organisation=organisation)
        if assigned:
            # We want to assign the contact to the case
            self.user = user
            if self.contact != user.contact and self.contact.email == user.contact.email:
                original_contact = self.contact
                self.contact = user.contact
                original_contact.delete()
                self.save()

                CaseContact.objects.get_or_create(
                    case=self.case,
                    contact=user.contact,
                    organisation=self.organisation,
                    defaults={"primary": False},
                )

        elif self.user:
            raise InvitationFailure("could not assign user to case or organisation")

        if accept:
            self.accepted()
            user.refresh_from_db()
            self.refresh_from_db()
        else:
            self.save()
        return assigned

    @transaction.atomic()
    def accept_invitation(self):
        """Accepting and processing the invitation when the invited user logs in"""
        if self.invitation_type == 1:
            # this is an own-org invitation
            self.contact.organisation.assign_user(
                user=self.invited_user,
                security_group=self.organisation_security_group,  # user or admin
                confirmed=True,
            )

        elif self.invitation_type == 2:
            # this is a representative invitation
            # First let's add the invitee as an admin user to their organisation
            security_group = Group.objects.get(name=SECURITY_GROUP_ORGANISATION_OWNER)
            self.contact.organisation.assign_user(
                user=self.invited_user, security_group=security_group, confirmed=True
            )

            # Then add them as a third party user of the inviting organisation
            security_group = Group.objects.get(name=SECURITY_GROUP_THIRD_PARTY_USER)
            self.organisation.assign_user(
                user=self.invited_user, security_group=security_group, confirmed=True
            )
        elif self.invitation_type == 3:
            # associate the user with the organisation
            self.organisation.assign_user(
                user=self.invited_user,
                security_group=self.organisation_security_group,  # user or admin
                confirmed=True,
            )

            # this is a caseworker invite, create a draft ROI for the case in question
            self.create_registration_of_interest(
                user=self.contact.user, organisation=self.organisation
            )

            # now associate the user with the case
            # Associating the organisation with the case
            OrganisationCaseRole.objects.get_or_create(
                organisation=self.organisation,
                case=self.case,
                defaults={
                    "role": self.case_role,
                    "sampled": True,
                    "created_by": self.user,
                },
            )

        # Let's add the user to the cases associated with this invitation
        for user_case_object in self.user_cases_to_link.all():
            # Creating the UserCase object
            # todo - maybe we do this when the LOA is approved instead???
            user_case_object.case.assign_user(
                user=self.invited_user,
                created_by=self.user,
                # We want the UserCase object to maintain the relationship between
                # interested party and representative
                organisation=user_case_object.organisation,
                relax_security=True,
            )

            # Creating an OrganisationCaseRole object with status awaiting_approval
            OrganisationCaseRole.objects.assign_organisation_case_role(
                organisation=self.contact.organisation,
                case=user_case_object.case,
                role=ROLE_AWAITING_APPROVAL,
                approved_at=None,  # approval done later
                approved_by=None,  # approval done later
            )

        # Now we mark the invitation as accepted
        self.accepted()

    def compare_user_contact(self):
        """
        Compare a user record with the associated invited contact.
        Returns a tuple of a boolean to determine if the user deviates from the contact data,
        and a dict detailing each difference between them.
        """
        deviation = False
        diff = {}
        if self.contact.name.upper() != self.user.name.upper():
            diff["name"] = {"contact": self.contact.name, "user": self.user.name}
        if self.contact.email.strip().upper() != self.user.email.strip().upper():
            diff["email"] = {"contact": self.contact.email, "user": self.user.email}
        if diff:
            deviation = True
        return deviation, diff
