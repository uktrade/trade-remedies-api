from django.db import models, transaction
from core.base import SimpleBaseModel, BaseModel
from core.models import UserProfile, User
from core.utils import convert_to_e164
from django_countries.fields import CountryField


class ContactManager(models.Manager):
    @staticmethod
    def create_contact(
        name,
        email,
        created_by,
        organisation=None,
        phone=None,
        post_code=None,
        country=None,
        address=None,
    ):
        """Create a new contact record

        Arguments:
            name {str} -- Contact name
            email {str} -- Contact email
            created_by {User} -- The user creating the contact

        Keyword Arguments:
            organisation {Organisation} -- Optional organisation
                   to associate the contact with (default: {None})
            phone {str} -- Contact phon enumber. Will be E164 formatted (default: {None})
            post_code {str} -- Contact post code (default: {None})
            country {str} -- Contact ISO country code (default: {None})

        Returns:
            Contact -- Contact model
        """
        contact = Contact(
            created_by=created_by,
            name=name,
            email=email.lower() if email else None,
            user_context=created_by,
        )
        country = (
            country or organisation.country.code if organisation and organisation.country else "GB"
        )
        contact.organisation = organisation
        if address is None and organisation:
            contact.address_from_org(organisation)
        else:
            contact.address = address
        contact.phone = convert_to_e164(phone, country)
        contact.country = country
        contact.post_code = post_code
        contact.save()
        return contact


class Contact(BaseModel):
    name = models.CharField(max_length=250, null=False, blank=False)
    organisation = models.ForeignKey(
        "organisations.Organisation", null=True, blank=True, on_delete=models.PROTECT
    )
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=80, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    post_code = models.CharField(max_length=16, null=True, blank=True)
    country = CountryField(blank_label="Select Country", null=True, blank=True)
    draft = models.BooleanField(default=False)

    objects = ContactManager()

    def __str__(self):
        return self.name

    def is_primary(self, case):
        if case:
            return CaseContact.objects.filter(case=case, contact=self, primary=True).exists()
        return False

    @property
    def has_user(self):
        """
        Returns true if the contact has a user associated with it.
        At this stage the caseworker will not be able to edit this contact's email
        or other contact details.
        """
        try:
            return bool(self.userprofile)
        except UserProfile.DoesNotExist:
            return False

    @property
    def user(self):
        try:
            return self.userprofile.user
        except (UserProfile.DoesNotExist, User.DoesNotExist):
            return None

    def _to_dict(self, case=None):
        base_dict = self.to_embedded_dict(case=case)
        base_dict.update(
            {
                "primary": self.is_primary(case),
                "phone": self.phone,
                "address": self.address,
                "post_code": self.post_code,
                "country": {
                    "name": self.country.name if self.country else None,
                    "code": self.country.code if self.country else None,  # noqa
                },
            }
        )
        return base_dict

    def to_embedded_dict(self, case=None):
        has_user = self.has_user
        _dict = self.to_minimal_dict()
        fields = {
            "Organisation": {
                "id": 0,
                "name": 0,
                "address": 0,
                "companies_house_id": 0,
                "country": 0,
            }
        }
        _dict.update(
            {
                "organisation": self.organisation.to_embedded_dict(fields=fields)
                if self.organisation
                else {},
                "has_user": has_user,
            }
        )
        if has_user:
            user = self.userprofile.user
            user_organisation = user.organisation
            user_dict = {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "organisation": user_organisation.to_embedded_dict() if user_organisation else {},
            }
            _dict["user"] = user_dict  # noqa
        return _dict

    def to_minimal_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "email": self.email,
        }

    @transaction.atomic
    def add_to_case(self, case, organisation=None, primary=False):
        """
        Add this contact to a case representing the given organisation
        (if provided, default to the contact's one).
        If set to primary=True, all others contacts in the case for that organisation will be set to
        non-primary
        """
        organisation = organisation or self.organisation
        case_contact, _ = CaseContact.objects.get_or_create(
            contact=self, case=case, organisation=organisation
        )
        if primary:
            self.set_primary(case, organisation=organisation)
        return case_contact

    def remove_from_case(self, case, organisation=None):
        """
        Remove this contact from a case
        """
        contact_case = self.casecontact_set.filter(contact=self, case=case)
        if organisation:
            contact_case = contact_case.filter(organisation=organisation)
        contact_case.delete()

    @transaction.atomic
    def set_primary(self, case, organisation=None, request_by=None):
        """
        Set this contact as primary for the organisation in a case, while setting all others in the
        organisation for that case to non-primary
        """
        organisation = organisation or self.organisation
        CaseContact.objects.filter(case=case, primary=True, organisation=organisation).update(
            primary=False
        )
        try:
            case_contact = self.casecontact_set.get(
                contact=self,
                case=case,
                organisation=organisation,
            )
        except self.casecontact_set.model.DoesNotExist:
            case_contact = self.casecontact_set.create(
                contact=self,
                case=case,
                organisation=organisation,
                user_context=request_by,
            )
        case_contact.primary = True
        case_contact.save()
        return case_contact

    def address_from_org(self, organisation=None):
        """Copy the address from a given organisation, or the contact's own
        organisation if one is not provided.

        Keyword Arguments:
            organisation {Organisation} -- Organisation model (default: {None})

        Returns:
            Contact -- Returns the current instance
        """
        organisation = organisation or self.organisation
        if organisation:
            self.address = organisation.address
            self.post_code = organisation.post_code
            self.country = organisation.country
        return self


class CaseContact(SimpleBaseModel):
    """
    Reference the association of contacts to a case, and whether they are the primary contact.
    A contact is associated with a case in relation to an organisation represented in the case.
    For example, a law firm might represent client A, applying for the case on their behalf.
    The contact associated with the application is the contact of the law firm, but associated
    with the case here using the represented organisation.
    """

    case = models.ForeignKey("cases.Case", null=False, blank=False, on_delete=models.PROTECT)
    contact = models.ForeignKey(Contact, null=False, blank=False, on_delete=models.PROTECT)
    organisation = models.ForeignKey(
        "organisations.Organisation", null=True, blank=True, on_delete=models.PROTECT
    )
    primary = models.BooleanField(default=False)

    class Meta:
        unique_together = ["case", "contact", "organisation"]

    def __str__(self):
        primary_indicator = " *" if self.primary else ""
        return f"{self.contact.name} [{self.organisation}] for {self.case.name}{primary_indicator}"
