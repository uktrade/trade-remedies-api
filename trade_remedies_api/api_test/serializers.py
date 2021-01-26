from rest_framework import serializers
from core.models import User

from cases.models import (
    Case,
    CaseType,
    CaseStage,
    CaseWorkflow,)

from organisations.models import Organisation

from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    ROLE_APPLICANT,
)

TEST_EMAIL = "ttt.aaa@d.com"
TEST_PASSWORD = "A7Hhfa!jfaw@f"



class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    organisations = OrganisationSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "organisations"]
    def create(self, validated_data):
        email = validated_data.pop("email")

        user = User.objects.create_user(
            name="test user",
            email=email,
            password=TEST_PASSWORD,
            groups=[SECURITY_GROUP_ORGANISATION_OWNER],
            country="GB",
            timezone="Europe/London",
            phone="012345678",
            organisation_name="Test Organisation",
            organisation_country="GB",
            companies_house_id="TE5 TS1",
            organisation_address="Test address",
        )
        return user


class CaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = ["id", "name"]

    def create(self, validated_data):
        user_email = validated_data.get("email", TEST_EMAIL)
        user_owner = User.objects.get(email=user_email)
        organisation_id = user_owner.organisation.organisation_id
        organisation = Organisation.objects.get(pk=organisation_id)
        case_type = CaseType.objects.get(acronym="AD")
        case = Case.objects.create(
            name="Test Case",
            created_by=user_owner,
            type=case_type
        )
        CaseWorkflow.objects.snapshot_from_template(case, case.type.workflow)
        organisation.assign_case(case, ROLE_APPLICANT)
        case.assign_organisation_user(user_owner, organisation)
        return case
