import logging
import uuid
from core.services.base import TradeRemediesApiView, ResponseSuccess
from core.services.exceptions import InvalidRequestParams, NotFoundApiExceptions
from django.utils import timezone, crypto
from django.db import transaction
from rest_framework import status
from invitations.models import Invitation
from contacts.models import Contact
from security.models import get_role, CaseRole, Group
from security.constants import SECURITY_GROUP_THIRD_PARTY_USER
from cases.models import (
    Case,
    Submission,
    SubmissionDocumentType,
    get_submission_type,
    get_case,
)
from core.utils import convert_to_e164
from cases.constants import (
    SUBMISSION_TYPE_INVITE_3RD_PARTY,
    SUBMISSION_DOCUMENT_TYPE_TRA,
)
from organisations.models import Organisation
from documents.models import DocumentBundle


logger = logging.getLogger(__name__)


class InvitationAPIView(TradeRemediesApiView):
    """
    Get a single invitations details by id

    `GET /api/v1/invitations/{invitation_id}/`
    Show a invitation details, only if the request comes from a TRA
    user or the invited user.
    """

    def get(self, request, invitation_id=None, *args, **kwargs):
        try:
            invitation = Invitation.objects.get(id=invitation_id, user=request.user)
            return ResponseSuccess({"result": invitation.to_dict()})
        except Invitation.DoesNotExist:
            raise NotFoundApiExceptions("Invalid invitation")


class InvitationsAPIView(TradeRemediesApiView):
    """
    Get and create Invitations for consultants and respondents

    `GET /api/v1/invitations/{invitation_id}/`
    Get an invite, if permissions allow (either a TRA user or an owner level of the inviting org)

    `GET /api/v1/invitations/`
    Show a contact's pending invitations

    `GET /api/v1/invitations/case/{case_id}/`
    Show a invitaitons for a case

    `GET /api/v1/invitations/case/{case_id}/submission/{submission_id}/`
    Show invitations made under a specific submission

    `POST /api/v1/invitations/invite/{contact_id}/to/{case_id}/as/{case_role_id}/`
    Invite a contact to a case as a given role.

    `DELETE /api/v1/invitations/{invitation_id}/`
    Delete an invitation
    """

    def get(
        self,
        request,
        case_id=None,
        contact_id=None,
        submission_id=None,
        invitation_id=None,
        organisation_id=None,
        *args,
        **kwargs,
    ):
        if invitation_id:
            invitation = Invitation.objects.get_user_invite(
                invitation_id, requested_by=request.user
            )
            return ResponseSuccess({"result": invitation.to_dict()})

        invitations = Invitation.objects.filter(deleted_at__isnull=True, organisation__isnull=False)
        if contact_id:
            try:
                contact = Contact.objects.select_related("userprofile", "organisation").get(
                    id=contact_id
                )
            except Contact.DoesNotExist:
                raise NotFoundApiExceptions("Invalid contact id.")
            invitations = invitations.filter(contact=contact)
        if case_id:
            try:
                case = Case.objects.get(id=case_id)
            except Case.DoesNotExist:
                raise InvalidRequestParams("Invalid case id")
            invitations = invitations.filter(case=case)
        if submission_id:
            submission = Submission.objects.get(id=submission_id)
            invitations = invitations.filter(submission=submission)
        return ResponseSuccess({"results": [invitation.to_dict() for invitation in invitations]})

    @transaction.atomic
    def post(
        self, request, contact_id, case_id, case_role_id=None, submission_id=None, *args, **kwargs
    ):
        notify_template_key = None
        try:
            contact = Contact.objects.select_related("userprofile", "organisation").get(
                id=contact_id
            )
            case_role = get_role(case_role_id)
            case = Case.objects.get(id=case_id)
            notify_template_key = case.type.meta.get("invite_notify_template_key")
        except Contact.DoesNotExist:
            raise NotFoundApiExceptions("Invalid contact id.")
        except CaseRole.DoesNotExist:
            raise NotFoundApiExceptions("Invalid case role id")
        except Case.DoesNotExist:
            raise InvalidRequestParams("Invalid case id")
        if not contact.organisation and contact.has_user:
            contact.organisation = contact.user.organisation.organisation
        # check if an invite exists already
        created = False
        invitation_kwargs = {}
        if submission_id:
            invitation_kwargs["submission__id"] = submission_id
        organisation_id = request.data.get("organisation_id")
        if organisation_id:
            organisation = Organisation.objects.get(id=organisation_id)
        else:
            organisation = contact.organisation
        try:
            invitation = Invitation.objects.get(
                contact=contact,
                case=case,
                organisation=organisation,
                deleted_at__isnull=True,
                **invitation_kwargs,
            )
        except Invitation.DoesNotExist:
            invitation = Invitation.objects.create(
                created_by=request.user,
                contact=contact,
                case=case,
                case_role=case_role,
                organisation=organisation,
                short_code=crypto.get_random_string(8),
                code=str(uuid.uuid4()),
                email=contact.email,
            )
            created = True
        values = {key: request.data.get(key) for key in request.data.keys()}
        invitation.send(
            sent_by=request.user, context=values, direct=True, template_key=notify_template_key
        )
        return ResponseSuccess(
            {
                "result": invitation.to_dict(),
                "created": created,
            },
            http_status=status.HTTP_201_CREATED,
        )

    def delete(self, request, invitation_id, *args, **kwargs):
        try:
            invitation = Invitation.objects.get(id=invitation_id)
        except Invitation.DoesNotExist:
            raise NotFoundApiExceptions("Invalid invitation id")
        invitation.delete()
        return ResponseSuccess({"deleted_id": invitation_id})


class InvitationDetailsAPI(TradeRemediesApiView):
    """
    Retrieve the details of an invitation. This call would normally be called
    via the trusted user (healthcheck) and used to display the invitation information
    in the invite welcome screen.

    `GET /api/v1/invitation/{code_id}/{case_id}/`
    Retrieve an invitation
    """

    def get(self, request, code=None, case_id=None, *args, **kwargs):
        try:
            case = Case.objects.get(id=case_id)
            invitation = Invitation.objects.get(code=code, case=case, deleted_at__isnull=True)
            return ResponseSuccess({"result": invitation.to_dict()})
        except Case.DoesNotExist:
            raise NotFoundApiExceptions("Invalid case id")
        except Invitation.DoesNotExist:
            raise NotFoundApiExceptions("Invalid invitation details")


class ValidateInvitationAPIView(TradeRemediesApiView):
    """
    Validate an invitation to an Organisation or case
    for a user

    `GET /invitations/{ORGANISATION_ID}/validate/`
    Validate a user (via email and/or user id) is invited to an organisation

    """

    def post(self, request, code=None, short_code=None, case_id=None, *args, **kwargs):
        if not code and not case_id and short_code:
            invitiation, organisation = Invitation.objects.validate_public_invite(
                short_code, user=request.user
            )
            return ResponseSuccess(
                {"result": {"invitation": invitiation.to_dict(), "deviation": None, "diff": None}}
            )
        else:
            invitation = Invitation.objects.get_invite_by_code(code, case_id)
            if invitation:
                invitation.process_invitation(request.user, accept=True)
                deviation, diff = invitation.compare_user_contact()
                return ResponseSuccess(
                    {
                        "result": {
                            "invitation": invitation.to_dict(),
                            "deviation": deviation,
                            "diff": diff,
                        }
                    }
                )
            else:
                raise NotFoundApiExceptions("No invitation found for this user")


class AcceptInvitationAPIView(TradeRemediesApiView):
    """
    Accept an invitation by a user

    `POST /invitations/{ORGANISATION_ID}/validate`
    Register an invitation as accepted after a user logs in and accepts
    """

    def post(self, request, invitation_id, *args, **kwargs):
        try:
            invitation = Invitation.objects.get(
                id=invitation_id,
                deleted_at__isnull=True,
            )
            invitation.accepted_at = timezone.now()
            invitation.user = request.user
            invitation.save()
            return ResponseSuccess(
                {
                    "result": invitation.to_dict(),
                }
            )
        except Invitation.DoesNotExist:
            raise NotFoundApiExceptions("Invitation not found")


class InviteThirdPartyAPI(TradeRemediesApiView):
    """
    Invite a 3rd party (e.g., lawyer) to a case, by a customer.
    This invite can encompass multiple people and is tied to a
    submission.
    """

    @staticmethod
    def get(request, case_id, submission_id, *args, **kwargs):
        case = Case.objects.get(id=case_id)
        submission = Submission.objects.get(case=case, id=submission_id)
        invites = Invitation.objects.filter(submission=submission)
        return ResponseSuccess({"results": [invite.to_dict() for invite in invites]})

    @staticmethod
    def build_submission(request_user, request_organisation, case):
        """Build submission for a Third Party invite.

        :param (User) request_user: Inviting user.
        :param (Organisation) request_organisation: inviting organisation.
        :param (Case) case: Case Third Party is being invited to.
        :returns (Submission): New Third Party submission.
        """
        # Create submission
        submission_type = get_submission_type(SUBMISSION_TYPE_INVITE_3RD_PARTY)
        submission_status = submission_type.default_status
        submission = Submission.objects.create(
            name="Invite 3rd party",
            type=submission_type,
            status=submission_status,
            organisation=request_organisation,
            case=case,
            created_by=request_user,
            contact=request_user.contact,
        )
        # Build submission documents
        case_bundle = DocumentBundle.objects.filter(
            case=case, submission_type=submission_type, status="LIVE"
        ).first()
        case_documents = case_bundle.documents.all() if case_bundle else []
        submission_document_type = SubmissionDocumentType.objects.get(
            id=SUBMISSION_DOCUMENT_TYPE_TRA
        )
        for case_document in case_documents:
            submission.add_document(
                document=case_document,
                document_type=submission_document_type,
                issued=False,
                issued_by=request_user,
            )
        return submission

    @staticmethod
    def build_invite(request_user, request_organisation, case, submission, request_data):
        """Build Third Party invite.

        :param (User) request_user: Inviting user.
        :param (Organisation) request_organisation: inviting organisation.
        :param (Case) case: Case Third Party is being invited to.
        :param (Submission) submission: Submission to encapsulate the invite.
        :param (dict) request_data: Invite parameters.
        """
        invitee_organisation = InviteThirdPartyAPI.get_invitee_org(request_user, request_data)
        contact = Contact.objects.create(
            name=request_data.get("name"),
            email=request_data.get("email", "").lower(),
            organisation=invitee_organisation,
            created_by=request_user,
        )
        third_party_group = Group.objects.get(name=SECURITY_GROUP_THIRD_PARTY_USER)
        invite = Invitation.objects.create(
            created_by=request_user,
            case=case,
            submission=submission,
            organisation=request_organisation,
            short_code=crypto.get_random_string(8),
            code=str(uuid.uuid4()),
            contact=contact,
            email=contact.email,
            organisation_security_group=third_party_group,
        )
        logger.info(f"Invite created: {invite}")

    @staticmethod
    def update_invite_contact(request_user, request_data, contact):
        """Update an existing Third Party invite contact.

        :param (User) request_user: Inviting user.
        :param (dict) request_data: Invite contact update parameters.
        :param (Contact) contact: Contact to update
        """
        contact.load_attributes(request_data, ["name", "email"])
        contact.organisation = InviteThirdPartyAPI.update_invitee_org(
            request_user, request_data, contact.organisation
        )
        if phone := request_data.get("phone"):
            contact.phone = convert_to_e164(phone)
        if contact.is_dirty(check_relationship=True):
            contact.save()

    @staticmethod
    def get_invitee_org(request_user, request_data):
        """Get Third Party Invitee's organisation.

        To avoid creating duplicate organisations where possible
        see if we can find one with same Name and Company ID.

        :param (User) request_user: Inviting user.
        :param (dict) request_data: Invite contact update parameters.
        :returns (Organisation): A new or existing organisation.
        """
        if requested_organisation := Organisation.objects.filter(
            name=request_data.get("organisation_name"),
            companies_house_id=request_data.get("companies_house_id"),
        ).first():
            return requested_organisation
        else:
            return Organisation.objects.create(
                created_by=request_user,
                user_context=[request_user],
                name=request_data.get("organisation_name"),
                companies_house_id=request_data.get("companies_house_id"),
                address=request_data.get("organisation_address"),
                country=request_data.get("country_code"),
            )

    @staticmethod
    def update_invitee_org(request_user, request_data, existing_organisation):
        """Update the Third Party Invitee's organisation.

        If the inviter updates organisation details, attempt to clean up.

        :param (User) request_user: Inviting user.
        :param (dict) request_data: Organisation update parameters.
        :param (Organisation) existing_organisation: Invitee's organisation.
        :returns (Organisation): The requested organisation.
        """
        requested_organisation = InviteThirdPartyAPI.get_invitee_org(request_user, request_data)
        can_edit_requested_organisation = not requested_organisation.has_users
        can_delete_existing_organisation = not existing_organisation.has_users
        if requested_organisation != existing_organisation:
            # Inviter specified an entirely different organisation, see if can we clean up.
            if can_delete_existing_organisation:
                logger.info(
                    f"Third Party Invite: Deleting unused organisation: {existing_organisation}"
                )
                try:
                    existing_organisation.delete(purge=True)
                except Organisation.DoesNotExist:
                    pass
                except Exception as e:
                    logger.error(
                        f"Failed to delete unused organisation {existing_organisation}: {e}"
                    )
        elif can_edit_requested_organisation:
            # An update to name or company number would have elicited a new org,
            # so just update address and country
            requested_organisation.address = request_data.get("organisation_address")
            requested_organisation.country = request_data.get("country_code")
            requested_organisation.save()
        return requested_organisation

    @transaction.atomic
    def post(self, request, case_id, organisation_id, submission_id=None, *args, **kwargs):
        case = Case.objects.get(id=case_id)
        # Get inviting organisation
        organisation = Organisation.objects.user_organisation(
            request.user, organisation_id=organisation_id
        )
        if not submission_id:
            submission = self.build_submission(request.user, organisation, case)
            self.build_invite(request.user, organisation, case, submission, request.data)
            return_status = status.HTTP_201_CREATED
        else:
            submission = Submission.objects.get(id=submission_id, organisation=organisation)
            invite = Invitation.objects.filter(submission=submission).first()
            if invite:
                self.update_invite_contact(request.user, request.data, invite.contact)
                return_status = status.HTTP_200_OK
            else:
                # No invite associated with submission (i.e. new version), rebuild the invite
                self.build_invite(request.user, organisation, case, submission, request.data)
                return_status = status.HTTP_201_CREATED
        return ResponseSuccess(
            {
                "result": {
                    "submission": submission.to_embedded_dict(),
                }
            },
            http_status=return_status,
        )

    def delete(self, request, case_id, submission_id, invite_id, *args, **kwargs):
        case = Case.objects.get(id=case_id)
        submission = Submission.objects.get(id=submission_id, case=case)
        invite = Invitation.objects.get(submission=submission, id=invite_id)
        invite.delete(purge=True)
        return ResponseSuccess({"result": {"id": str(invite_id), "deleted": True}})


class NotifyInviteThirdPartyAPI(TradeRemediesApiView):
    def post(self, request, case_id, submission_id, contact_id, *args, **kwargs):
        notify_data = request.data.dict()
        case = get_case(case_id)
        submission = Submission.objects.get(id=submission_id, case=case)
        contact = Contact.objects.select_related("userprofile", "organisation").get(id=contact_id)
        try:
            invite = Invitation.objects.get(submission=submission, contact=contact)
        except Invitation.DoesNotExist:
            raise NotFoundApiExceptions("Invite not found")
        send_report = invite.send(
            sent_by=request.user,
            context=notify_data,
            direct=True,
            template_key="NOTIFY_THIRD_PARTY_INVITE",
        )
        invite.email_sent = True
        invite.sent_at = timezone.now()
        invite.approved_by = request.user
        invite.save()
        return ResponseSuccess({"result": invite.to_dict()}, http_status=status.HTTP_201_CREATED)


class ValidateUserInviteAPIView(TradeRemediesApiView):
    def get(self, request, code, organisation_id, *args, **kwargs):
        try:
            organisation = Organisation.objects.get(id=organisation_id)
            invite = Invitation.objects.get(
                code=code, organisation=organisation, deleted_at__isnull=True
            )
            invited_by = invite.created_by
            invited_by_token = invited_by.auth_token.key
        except (Organisation.DoesNotExist, Invitation.DoesNotExist):
            raise NotFoundApiExceptions("Invite not found")
        response = {"organisation": organisation.to_embedded_dict(), "invite": invite.to_dict()}
        response["invite"]["invited_by"] = invited_by_token

        return ResponseSuccess({"result": response}, http_status=status.HTTP_200_OK)


class UserInvitations(TradeRemediesApiView):
    def get(self, request, invite_id=None, *args, **kwargs):
        invites = (
            Invitation.objects.filter(organisation=request.user.organisation.organisation)
            .exclude(accepted_at__isnull=False)
            .exclude(case__isnull=False)
            .exclude(deleted_at__isnull=False)
        )
        return ResponseSuccess({"results": [invite.to_dict() for invite in invites]})
