import requests
from django.contrib.auth.models import Group
from django.db.models import F
from rest_framework import serializers

from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST
from config.serializers import CustomValidationModelSerializer
from contacts.models import CaseContact, Contact
from contacts.services.v2.serializers import CaseContactSerializer
from core.services.ch_proxy import COMPANIES_HOUSE_BASE_DOMAIN, COMPANIES_HOUSE_BASIC_AUTH
from core.services.v2.users.serializers import ContactSerializer, UserSerializer
from organisations.models import Organisation
from security.models import CaseRole, OrganisationCaseRole, OrganisationUser, UserCase
from django_restql.fields import NestedField


class OrganisationCaseRoleSerializer(CustomValidationModelSerializer):
    case = serializers.SerializerMethodField()
    validated_by = UserSerializer(fields=["name", "email"], required=False)
    role_name = serializers.CharField(source="role.name")
    auth_contact = NestedField(serializer_class=ContactSerializer, required=False, accept_pk=True)

    class Meta:
        model = OrganisationCaseRole
        fields = "__all__"
        extra_kwargs = {"case": {"read_only": True}, "organisation": {"read_only": True}}

    def to_internal_value(self, data):
        data = data.copy()  # Making the QueryDict mutable
        if role_key := data.get("role_key"):
            # We can pass a role_key in the request.POST which we can use to lookup a CaseRole obj
            role_object = CaseRole.objects.get(key=role_key)
            data["role"] = role_object.pk
        return super().to_internal_value(data)

    @staticmethod
    def get_case(instance):
        # This needs to be a SerializerMethodField to avoid the circular import of CaseSerializer
        from cases.services.v2.serializers import CaseSerializer

        return CaseSerializer(instance=instance.case).data


class OrganisationUserSerializer(CustomValidationModelSerializer):
    class Meta:
        model = OrganisationUser
        fields = "__all__"

    user = UserSerializer()
    security_group = serializers.SlugRelatedField(slug_field="name", queryset=Group.objects.all())


class OrganisationSerializer(CustomValidationModelSerializer):
    country = serializers.CharField(source="country.alpha3", required=False)
    country_code = serializers.ReadOnlyField(source="country.code")
    organisationuser_set = OrganisationUserSerializer(many=True, required=False)
    cases = serializers.SerializerMethodField()
    invitations = serializers.SerializerMethodField()
    validated = serializers.SerializerMethodField()
    organisationcaserole_set = OrganisationCaseRoleSerializer(many=True, required=False)
    user_cases = serializers.SerializerMethodField()
    does_name_match_companies_house = serializers.SerializerMethodField()
    case_contacts = serializers.SerializerMethodField()
    representative_cases = serializers.SerializerMethodField()
    contacts = serializers.SerializerMethodField()
    representative_contacts = serializers.SerializerMethodField()
    country_name = serializers.ReadOnlyField(source="country.name")
    rejected_cases = serializers.SerializerMethodField()
    json_data = serializers.JSONField(required=False, allow_null=True)
    a_tag_website_url = serializers.SerializerMethodField()

    def to_representation(self, instance):
        instance.json_data = {}
        return super().to_representation(instance)

    class Meta:
        model = Organisation
        fields = "__all__"

    @staticmethod
    def get_a_tag_website_url(instance):
        """Returns the URL of the org's website with http:// prepended so it can be used in a tag"""
        if instance.organisation_website and not instance.organisation_website.startswith("http"):
            return f"http://{instance.organisation_website}"
        return instance.organisation_website

    @staticmethod
    def get_rejected_cases(instance):
        """Return all instances when this organisation was rejected from a case"""
        from invitations.models import Invitation
        from cases.services.v2.serializers import CaseSerializer

        rejections = []

        # finding the rep invitations for this org which have been rejected
        rejected_invitations = Invitation.objects.filter(
            contact__organisation=instance,
            rejected_by__isnull=False,
            rejected_at__isnull=False,
            invitation_type=2,  # only rep invites
        )
        for invitation in rejected_invitations:
            rejections.append(
                {
                    "case": CaseSerializer(
                        invitation.submission.case, fields=["name", "reference"]
                    ).data,
                    "date_rejected": invitation.rejected_at,
                    "rejected_reason": invitation.submission.deficiency_notice_params.get(
                        "explain_why_contact_org_not_verified", ""
                    ),
                    "rejected_by": UserSerializer(
                        invitation.rejected_by, fields=["name", "email"]
                    ).data,
                    "invitation_id": invitation.id,
                }
            )

        return rejections

    def get_representative_cases(self, instance):
        """Return all cases where this Organisation is acting as a representative"""
        representations = []
        # first let's get the cases where this organisation has been invited as a representative
        from cases.models import Submission
        from cases.services.v2.serializers import CaseSerializer
        from invitations.models import Invitation

        representative_case_contacts = (
            CaseContact.objects.filter(
                contact__organisation=instance,
            )
            .exclude(contact__organisation=F("organisation"))
            .distinct("case")
        )
        for case_contact in representative_case_contacts:
            try:
                corresponding_org_case_role = OrganisationCaseRole.objects.get(
                    organisation=case_contact.organisation, case=case_contact.case
                )
            except OrganisationCaseRole.DoesNotExist:
                continue
            representation = {
                "on_behalf_of": case_contact.organisation.name,
                "case": CaseSerializer(case_contact.case).data,
                "role": corresponding_org_case_role.role.name,
            }
            # now we need to find if this case_contact has been created as part of an ROI or an invitation
            invitation = (
                Invitation.objects.filter(
                    contact__organisation=instance,
                    case=case_contact.case,
                    organisation=case_contact.organisation,
                )
                .order_by("-last_modified")
                .first()
            )
            if invitation:
                representation.update(
                    {
                        "validated": invitation.submission.deficiency_notice_params.get(
                            "contact_org_verify", False
                        )
                        if invitation.submission.deficiency_notice_params
                        else False,
                        "validated_at": invitation.submission.deficiency_notice_params.get(
                            "contact_org_verify_at", None
                        )
                        if invitation.submission.deficiency_notice_params
                        else None,
                    }
                )
                representations.append(representation)
            else:
                # maybe it's an ROI that got them here
                try:
                    (
                        Submission.objects.filter(
                            type_id=SUBMISSION_TYPE_REGISTER_INTEREST,
                            contact__organisation=instance,
                            case=case_contact.case,
                            organisation=case_contact.organisation,
                        )
                        .order_by("-last_modified")
                        .first()
                    )
                    representation.update(
                        {
                            "validated": bool(corresponding_org_case_role.validated_at),
                            "validated_at": corresponding_org_case_role.validated_at,
                        }
                    )
                    representations.append(representation)
                except Submission.DoesNotExist:
                    ...
                    # todo - log error here, how do they have access to this case

        return representations

    @staticmethod
    def get_case_contacts(instance):
        """
        Return all CaseContact objects where the contact belongs to this organisation.

        In this way we can find all the cases where this organisation is representing another org."""
        case_contacts = CaseContact.objects.filter(contact__organisation=instance)
        return CaseContactSerializer(instance=case_contacts, many=True).data

    @staticmethod
    def get_does_name_match_companies_house(instance):
        """Checks if the company name on Companies House matches the company name in the DB"""
        if registration_number := instance.companies_house_id:
            if organisation_name := instance.name:
                headers = {"Authorization": f"Basic {COMPANIES_HOUSE_BASIC_AUTH}"}
                response = requests.get(
                    f"{COMPANIES_HOUSE_BASE_DOMAIN}/company/{registration_number}",
                    headers=headers,
                )
                if response.status_code == 200:
                    if (
                        response.json().get(
                            "company_name",
                        )
                        == organisation_name
                    ):
                        return True
        return False

    @staticmethod
    def get_user_cases(instance):
        user_cases = UserCase.objects.filter(
            user__organisationuser__organisation=instance,
            case__deleted_at__isnull=True,
            case__archived_at__isnull=True,
        )

        from security.services.v2.serializers import UserCaseSerializer

        return UserCaseSerializer(user_cases, many=True).data

    def get_cases(self, instance):
        """Return all cases that this organisation is a part of."""
        from cases.services.v2.serializers import CaseSerializer

        from cases.models import Case

        user_cases = UserCase.objects.filter(
            user__organisationuser__organisation=instance,
            case__deleted_at__isnull=True,
            case__archived_at__isnull=True,
        ).select_related("case")
        if request := self.context.get("request", None):
            if not request.user.is_tra():
                cases = user_cases.filter(user=request.user)

        cases = Case.objects.filter(usercase__in=user_cases).distinct()
        return CaseSerializer(cases, many=True).data

    def get_invitations(self, instance):
        """Return all invitations that this organisation has sent."""
        from invitations.services.v2.serializers import InvitationSerializer

        return [
            InvitationSerializer(
                instance=each, exclude=["organisation"]  # Avoid infinite self-referencing
            ).data
            for each in instance.invitation_set.all().select_related(
                "organisation", "contact", "submission"
            )
        ]

    def get_validated(self, instance):
        """Returns true if the organisation has been validated on the TRS at some point"""
        return instance.organisationcaserole_set.filter(validated_at__isnull=False).exists()

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if "country" in data and isinstance(data["country"], dict):
            data["country"] = data["country"]["alpha3"]
        return data

    @staticmethod
    def get_contacts(instance):
        from core.services.v2.users.serializers import ContactSerializer

        return ContactSerializer(instance.contacts.all(), many=True).data

    @staticmethod
    def get_representative_contacts(instance):
        """Returns all contacts that are representing this organisation"""
        from core.services.v2.users.serializers import ContactSerializer

        contacts = Contact.objects.filter(casecontact__organisation=instance)
        return ContactSerializer(instance=contacts, many=True).data
