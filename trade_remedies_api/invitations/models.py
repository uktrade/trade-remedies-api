import uuid
from django.db import models, transaction
from django.conf import settings
from core.base import BaseModel
from django.contrib.auth.models import Group
from django.contrib.postgres import fields
from django.utils import timezone, crypto
from cases.models import get_case
from organisations.models import get_organisation
from core.tasks import send_mail
from core.models import SystemParameter
from core.utils import convert_to_e164
from contacts.models import Contact, CaseContact
from audit.utils import audit_log
from audit import AUDIT_TYPE_NOTIFY, AUDIT_TYPE_EVENT
from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    ROLE_PREPARING,
)
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

    def get_invite_by_code(self, code, case_id):
        """
        Validate an invitation exists for user/code/case combination.
        """
        case = get_case(case_id)
        invitation = (
            self.select_related("submission", "submission__organisation", "organisation", "contact")
            .filter(code=code, case=case, accepted_at__isnull=True, deleted_at__isnull=True)
            .first()
        )
        return invitation

    def validate_all_pending(self, user, code=None, case_id=None):
        """
        validate all pending invitations for a user.
        If code and case are provided, prepare that invitation beforehand.
        """
        accepted = []
        if code and case_id:
            invitation = self.get_invite_by_code(code, case_id)
            if invitation:
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
                "login_url": f"{settings.PUBLIC_ROOT_URL}/invitation/{invite.code}/for/{organisation.id}/"  # noqa: E501
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

    An invite can be marked invalid which can happen
    if for example an existing public user is invited.
    A record of the invite still exists,
    but the user exercise it. Any temporary/permanent meta data
    related to the invite can be saved in the meta dict.
    """

    organisation = models.ForeignKey(
        "organisations.Organisation", null=True, blank=True, on_delete=models.PROTECT
    )
    organisation_security_group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.PROTECT
    )
    contact = models.ForeignKey("contacts.Contact", null=True, blank=True, on_delete=models.PROTECT)
    case = models.ForeignKey("cases.Case", null=True, blank=True, on_delete=models.PROTECT)
    submission = models.ForeignKey(
        "cases.Submission", null=True, blank=True, on_delete=models.PROTECT
    )
    case_role = models.ForeignKey(
        "security.CaseRole", null=True, blank=True, on_delete=models.PROTECT
    )
    user = models.ForeignKey("core.User", null=True, blank=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=250, null=True, blank=True)
    email = models.EmailField(null=False, blank=False)
    invalid = models.BooleanField(default=False)
    code = models.CharField(max_length=50, null=True, blank=True, unique=True)
    short_code = models.CharField(max_length=16, null=True, blank=True, unique=True)
    email_sent = models.NullBooleanField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "core.User", null=True, blank=True, on_delete=models.PROTECT, related_name="approved"
    )
    meta = fields.JSONField(default=dict)

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

    def send(self, sent_by, context=None, direct=False, template_key=None):
        """Send the invite email via notify

        Arguments:
            sent_by {User} -- The user sending the invitation

        Keyword Arguments:
            context {dict} -- extra context dict (default: {None})
            direct {bool} -- include a direct login link with the invite codes (default: {False})
            template_key {str} -- The system param pointing to the template id (default: {None})

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
            "footer": SystemParameter.get("NOTIFY_BLOCK_FOOTER"),
            "email": SystemParameter.get("TRADE_REMEDIES_EMAIL"),
            "invited_by": self.created_by.name,
        }
        if self.case:
            product = self.case.product_set.first()
            export_source = self.case.exportsource_set.first()
            case_name = self.case.name or (product.sector.name if product else "N/A")
            registration_deadline = self.case.registration_deadline
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
                    "deadline": registration_deadline.strftime(settings.FRIENDLY_DATE_FORMAT)
                    if registration_deadline
                    else "N/A",
                    "invited_by_name": self.submission.contact.name if self.submission else "",
                    "invited_by_organisation": self.submission.organisation.name
                    if self.submission
                    else "",
                }
            )
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

    @transaction.atomic  # noqa:C901
    def process_invitation(
        self,
        user,
        accept=False,
        organisation=None,
        assign_to_organisation=False,
        register_interest=False,
    ):
        """
        Process an invitation for a user. An invitation is usually generated by another user
        inviting this user to his view of the case (silo).
        The user will be added to the case under the inviting organisation.

        By default the invitation is not accepted unless accept is True. This is
        done on first login where all pending invites are accepted.
        Generic invites, which are not tied to a specific user will not be updated
        with the invite details.

        By default, the user will not become a user of the organisation. This is only reserved for
        situations where the TRA are inviting a user they have added as a party themselves.

        If register_interest is True, a registration of interest will be created for this user
        for the case represented in the invite. If the user arrives without an organisation
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
                assigned = True
        # if a registration of interest is to be created, do it now.
        if register_interest:
            submission_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_REGISTER_INTEREST)
            reg_interest = Submission(
                created_by=user,
                name=submission_type.name,
                type=submission_type,
                status=submission_type.default_status,
                organisation=organisation,
                case=self.case,
                contact=user.contact,
                user_context=user,
            )
            reg_interest.save()
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
        else:
            assigned = self.assign_case_user(user=user, organisation=organisation)
        if assign_to_organisation:
            self.assign_organisation_user(user=user, organisation=organisation)
        if assigned:
            self.user = user
            if self.contact != user.contact and self.contact.email == user.contact.email:
                CaseContact.objects.get_or_create(
                    case=self.case,
                    contact=user.contact,
                    organisation=self.organisation,
                    primary=False,
                )
                original_contact = self.contact
                self.contact = user.contact
                original_contact.delete()
                self.save()

            if accept:
                self.accepted()
                self.user.refresh_from_db()
                self.refresh_from_db()
            else:
                self.save()
        elif self.user:
            raise InvitationFailure("could not assign user to case or organisation")
        return assigned

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
