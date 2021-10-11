from django.utils import timezone

from rest_framework import serializers
from core.models import User

from cases.models import (
    Case,
    CaseType,
    CaseWorkflow,
)

from cases.models import (
    Product,
    ExportSource,
    Sector,
)

from organisations.models import Organisation

from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    ROLE_APPLICANT,
)

from security.models import OrganisationCaseRole

TEST_EMAIL = "ttt.aaa@d.com"  # /PS-IGNORE
TEST_PASSWORD = "A7Hhfa!jfaw@f"


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "name"]


def create_user(email):
    """create a user.
    It creates a test organisation for the user.
    """
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


class UserSerializer(serializers.ModelSerializer):
    organisations = OrganisationSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "organisations"]

    def create(self, validated_data):
        email = validated_data.pop("email")
        return create_user(email)


class CaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = ["id", "name"]

    def create(self, validated_data):
        """create.

        Creates a test Case for an organisation user.
        Creates the organisation user if it doesn't exist. The user is the applicant.
        Creates all the objects required for a valid case:
            workflow
            product
            export source
        The case is initiated so it will be available in the list of cases in public
        :param (dict) validated_data: user email.
        """
        user_email = validated_data.get("email", TEST_EMAIL)

        user_owner = User.objects.filter(email=user_email).first()
        if not user_owner:
            user_owner = create_user(user_email)

        organisation_id = user_owner.organisation.organisation_id
        organisation = Organisation.objects.get(pk=organisation_id)
        case_type = CaseType.objects.get(acronym="AD")
        case = Case.objects.create(name="Test Case", created_by=user_owner, type=case_type)
        CaseWorkflow.objects.snapshot_from_template(case, case.type.workflow)
        organisation.assign_case(case, ROLE_APPLICANT)
        case.assign_organisation_user(user_owner, organisation)
        case_id = case.id
        # get a sector for the product
        sector = Sector.objects.all().first()
        # create a product
        product = Product.objects.create(
            case=case, name="TP", sector=sector, description="Test Product",
        )
        # and an export source
        export_source = ExportSource.objects.create(
            case=case, country="AL", last_modified=timezone.now()
        )
        caserole = OrganisationCaseRole.objects.get(case=case)
        caserole.approved_at = timezone.now()
        caserole.save()

        # set initiated date to make it appears in the list of cases on public
        case.initiated_at = timezone.now()
        case.save()
        return case
