from core.services.base import TradeRemediesApiView, ResponseSuccess
from core.services.exceptions import (
    NotFoundApiExceptions,
    RequestValidationError,
)
from cases.models import get_case
from core.utils import pluck, is_valid_email
from rest_framework import status
from contacts.models import Contact, CaseContact
from organisations.models import Organisation


class ContactsAPI(TradeRemediesApiView):
    """
    Return all or one contact records

    `GET /contacts/`
    Return all contact records, allowing for filtering by organisation, name or address
    `GET /contact/{contact_id}/`
    Return a single contact record

    `POST /contact/`
    Create a new contact
    `POST /contact/{contact_id}/`
    Update a contact

    """

    def get(self, request, contact_id=None, *args, **kwargs):
        if contact_id:
            try:
                contact = Contact.objects.select_related("userprofile", "organisation").get(
                    id=contact_id
                )
                return ResponseSuccess({"result": contact.to_dict()})
            except Contact.DoesNotExist:
                raise NotFoundApiExceptions("Contact does not exist or access is denied")
        else:
            filter_kwargs = pluck(request.query_params, ["name", "country", "organisation"])
            contacts = Contact.objects.filter(**filter_kwargs)
        return ResponseSuccess({"results": [_contact.to_dict() for _contact in contacts]})

    def post(  # noqa: C901
        self, request, contact_id=None, organisation_id=None, case_id=None, *args, **kwargs
    ):
        self.required_keys = ["contact_name"]
        if not self.feature_flags("contact_email_read_only"):
            self.required_keys.append("contact_email")
        case_id = case_id or request.data.get("case_id")
        organisation_id = organisation_id or request.data.get("organisation_id")
        missing_required_fields = self.validate_required_fields(request)
        errors = {fld: "Required" for fld in missing_required_fields}
        if not self.feature_flags("contact_email_read_only"):
            if not is_valid_email(request.data.get("contact_email", "")):
                errors["email_not_valid"] = "Invalid email format"
        if errors:
            raise RequestValidationError(detail=errors)
        case = None
        if case_id:
            case = get_case(case_id)
        contact_id = contact_id or request.data.get("contact_id")
        if contact_id:
            try:
                contact = Contact.objects.select_related("userprofile", "organisation").get(
                    id=contact_id
                )
            except Contact.DoesNotExist:
                raise NotFoundApiExceptions("Contact does not exist or access is denied")
            if organisation_id:
                organisation = Organisation.objects.get(id=organisation_id)
                CaseContact.objects.get_or_create(
                    case=case, contact=contact, organisation=organisation, primary=False
                )
        else:
            organisation = None
            if organisation_id:
                organisation = Organisation.objects.get(id=organisation_id)
            contact = Contact(organisation=organisation, created_by=request.user)
        contact.set_case_context(case)
        contact.set_user_context(request.user)
        contact.name = request.data.get("contact_name")
        contact.address = request.data.get("contact_address")
        contact.country = request.data.get("contact_country")
        contact.post_code = request.data.get("contact_post_code")
        if not self.feature_flags("contact_email_read_only"):
            contact.email = request.data.get("contact_email", "").lower()
        contact.phone = request.data.get("contact_phone")
        if case and request.data.get("primary_contact"):
            contact.set_primary(case=case)
        contact.e_additional_invite_information = request.data.get("e_additional_invite_information")
        contact.save()
        return ResponseSuccess({"result": contact.to_dict()}, http_status=status.HTTP_201_CREATED)

    def delete(self, request, contact_id=None, *args, **kwargs):
        try:
            contact = Contact.objects.select_related("userprofile", "organisation").get(
                id=contact_id
            )
        except Contact.DoesNotExist:
            raise NotFoundApiExceptions("Contact does not exist or access is denied")
        CaseContact.objects.filter(contact=contact).delete()
        contact.delete()
        return ResponseSuccess({"result": {"deleted": True}}, http_status=status.HTTP_200_OK)


class ContactPrimaryAPI(TradeRemediesApiView):
    def post(self, request, case_id, contact_id, organisation_id, *args, **kwargs):
        try:
            contact = Contact.objects.select_related("userprofile", "organisation").get(
                id=contact_id
            )
        except Contact.DoesNotExist:
            raise NotFoundApiExceptions("Contact does not exist or access is denied")
        try:
            organisation = Organisation.objects.get(id=organisation_id)
        except Organisation.DoesNotExist:
            raise NotFoundApiExceptions("Organisation does not exist or access is denied")
        contact.set_primary(case=get_case(case_id), organisation=organisation)
        return ResponseSuccess({"result": contact.to_dict()}, http_status=status.HTTP_201_CREATED)


class ContactLookup(TradeRemediesApiView):
    def get(self, request):
        term = request.query_params.get("term")
        contacts = Contact.objects.filter(email__istartswith=term)
        results = [
            {"email": contact.email, "name": contact.name, "id": contact.id} for contact in contacts
        ]
        return ResponseSuccess({"results": results}, http_status=status.HTTP_201_CREATED)
