from django.contrib.auth.models import Group
from django.db.models import Q
from django_restql.fields import NestedField
from rest_framework import serializers

from config.serializers import CustomValidationModelSerializer
from contacts.models import CaseContact, Contact
from contacts.services.v2.serializers import CaseContactSerializer
from core.services.v2.users.serializers import ContactSerializer, UserSerializer
from organisations.models import (
    DuplicateOrganisationMerge,
    Organisation,
    OrganisationMergeRecord,
    SubmissionOrganisationMergeRecord,
)
from security.models import CaseRole, OrganisationCaseRole, OrganisationUser


class OrganisationCaseRoleSerializer(CustomValidationModelSerializer):
    case_role_key = serializers.SerializerMethodField()
    validated_by = UserSerializer(fields=["name", "email"], required=False)
    role_name = serializers.CharField(source="role.name", required=False)
    auth_contact = NestedField(serializer_class=ContactSerializer, required=False, accept_pk=True)
    organisation_name = serializers.CharField(source="organisation.name", required=False)

    class Meta:
        model = OrganisationCaseRole
        fields = "__all__"

    def to_internal_value(self, data):
        data = data.copy()  # Making the QueryDict mutable
        if role_key := data.get("role_key"):
            # We can pass a role_key in the request.POST which we can use to lookup a CaseRole obj
            role_object = CaseRole.objects.get(key=role_key)
            data["role"] = role_object.pk
        return super().to_internal_value(data)

    def to_representation(self, obj):
        from cases.services.v2.serializers import CaseSerializer

        ret = super().to_representation(obj)
        if isinstance(obj, OrganisationCaseRole):
            ret["case"] = CaseSerializer(instance=obj.case).data
        return ret

    @staticmethod
    def get_case_role_key(instance):
        return instance.role.key


class OrganisationUserSerializer(CustomValidationModelSerializer):
    class Meta:
        model = OrganisationUser
        fields = "__all__"

    user = UserSerializer()
    security_group = serializers.SlugRelatedField(slug_field="name", queryset=Group.objects.all())
    security_group_key = serializers.ReadOnlyField(source="security_group.key")


class OrganisationSerializer(CustomValidationModelSerializer):
    class Meta:
        model = Organisation
        fields = "__all__"

    country = serializers.CharField(source="country.alpha3", required=False)
    country_code = serializers.ReadOnlyField(source="country.code")
    organisationuser_set = OrganisationUserSerializer(many=True, required=False)
    cases = serializers.SerializerMethodField()
    validated = serializers.SerializerMethodField()
    organisationcaserole_set = OrganisationCaseRoleSerializer(many=True, required=False)
    user_cases = serializers.SerializerMethodField()
    case_contacts = serializers.SerializerMethodField()
    contacts = serializers.SerializerMethodField()
    representative_contacts = serializers.SerializerMethodField()
    case_count = serializers.IntegerField(required=False)
    country_name = serializers.ReadOnlyField(source="country.name")
    json_data = serializers.JSONField(required=False, allow_null=True)
    a_tag_website_url = serializers.SerializerMethodField()
    full_country_name = serializers.SerializerMethodField()

    def to_representation(self, instance):
        instance.json_data = {}
        return super().to_representation(instance)

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if "country" in data and isinstance(data["country"], dict):
            data["country"] = data["country"]["alpha3"]
        return data

    @staticmethod
    def get_a_tag_website_url(instance):
        """Returns the URL of the org's website with http:// prepended so it can be used in a tag"""
        if instance.organisation_website and not instance.organisation_website.startswith("http"):
            return f"http://{instance.organisation_website}"
        return instance.organisation_website

    @staticmethod
    def get_case_contacts(instance):
        """
        Return all CaseContact objects where the contact belongs to this organisation.

        In this way we can find all the cases where this organisation is representing another org.
        """
        case_contacts = CaseContact.objects.filter(contact__organisation=instance)
        return CaseContactSerializer(instance=case_contacts, many=True).data

    def get_user_cases(self, instance):
        from security.services.v2.serializers import UserCaseSerializer

        user_cases = instance.get_user_cases()
        if requesting_user := self.context.get("requesting_user"):
            # We want to filter the user cases
            # to only those that are visible to the requesting organisation
            if not requesting_user.is_tra():
                # We want to filter the user cases
                # to only those that are visible to the requesting organisation
                query_filter = Q(user=requesting_user)
                if requesting_user.contact.organisation:
                    query_filter = (
                        query_filter
                        | Q(organisation=requesting_user.contact.organisation)
                        | Q(
                            user__userprofile__contact__organisation=requesting_user.contact.organisation
                        )
                    )
                user_cases = user_cases.filter(query_filter)
        return UserCaseSerializer(user_cases, many=True).data

    def get_cases(self, instance):
        """Return all cases that this organisation is a part of."""
        from cases.services.v2.serializers import CaseSerializer

        from cases.models import Case

        user_cases = instance.get_user_cases().select_related("case")
        if request := self.context.get("request", None):
            if not request.user.is_tra():
                cases = user_cases.filter(user=request.user)

        cases = Case.objects.filter(usercase__in=user_cases).distinct()
        return CaseSerializer(cases, many=True).data

    @staticmethod
    def get_validated(instance):
        """Returns true if the organisation has been validated on the TRS at some point"""
        return instance.organisationcaserole_set.filter(validated_at__isnull=False).exists()

    @staticmethod
    def get_full_country_name(instance):
        """Return the full country name of the Organisation, e.g. GB --> Great Britain"""
        return instance.country.name if instance.country else None

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


skinny_organisation_fields = [
    "name",
    "address",
    "post_code",
    "country",
    "vat_number",
    "eori_number",
    "duns_number",
    "companies_house_id",
    "organisation_website",
    "country_name",
]


class DuplicateOrganisationMergeSerializer(CustomValidationModelSerializer):
    """Serializes DuplicateOrganisationMerge objects"""

    class Meta:
        model = DuplicateOrganisationMerge
        fields = "__all__"

    child_organisation = OrganisationSerializer(fields=skinny_organisation_fields)
    parent_organisation = OrganisationSerializer(
        fields=skinny_organisation_fields,
        source="merge_record.parent_organisation",
    )
    order_in_parent = serializers.SerializerMethodField()
    identical_fields = serializers.SerializerMethodField()

    @staticmethod
    def get_order_in_parent(instance):
        """Returns the order of this duplicate in the parent organisation along with number of
        total duplicates, e.g 3/10 possible duplicates.
        """
        all_duplicates = list(instance.merge_record.potential_duplicates())
        return (all_duplicates.index(instance), len(all_duplicates))

    @staticmethod
    def get_identical_fields(instance):
        """Returns a list of the fields that are identical
        between the parent and child organisation.
        """
        return instance.merge_record.parent_organisation.get_identical_fields(
            instance.child_organisation
        )


class OrganisationMergeRecordSerializer(CustomValidationModelSerializer):
    """Serializes OrganisationMergeRecord objects"""

    class Meta:
        model = OrganisationMergeRecord
        fields = "__all__"

    id = serializers.UUIDField(source="parent_organisation.id", read_only=True)
    parent_organisation = OrganisationSerializer(fields=skinny_organisation_fields)
    status_name = serializers.CharField(source="get_status_display")
    potential_duplicates = serializers.SerializerMethodField()

    @staticmethod
    def get_potential_duplicates(instance):
        """Returns all potential duplicates for this merge record"""
        return DuplicateOrganisationMergeSerializer(instance.potential_duplicates(), many=True).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["pending_potential_duplicates"] = [
            each for each in data["potential_duplicates"] if each["status"] == "pending"
        ]
        return data

    def save(self, **kwargs):
        """Override save to update the chosen_case_roles field with the chosen role_ids whilst keeping the old ones intact"""
        if chosen_case_roles := self.initial_data.get("chosen_case_roles_delimited", None):
            chosen_case_roles = chosen_case_roles.split("*-*")
            case_id = chosen_case_roles[1]
            role_id = chosen_case_roles[0]

            current_chosen_case_roles = self.instance.chosen_case_roles or {}
            current_chosen_case_roles[case_id] = role_id

            self.instance.chosen_case_roles = current_chosen_case_roles
        return super().save(**kwargs)


class SubmissionOrganisationMergeRecordSerializer(CustomValidationModelSerializer):
    class Meta:
        model = SubmissionOrganisationMergeRecord
        fields = "__all__"

    id = serializers.UUIDField(source="submission.id", read_only=True)
    organisation_merge_record = OrganisationMergeRecordSerializer()
    status_name = serializers.CharField(source="get_status_display")
    submission = serializers.SerializerMethodField()

    @staticmethod
    def get_submission(instance):
        from cases.services.v2.serializers import SubmissionSerializer

        return SubmissionSerializer(
            instance.submission,
            fields=[
                "case",
            ],
        ).data
