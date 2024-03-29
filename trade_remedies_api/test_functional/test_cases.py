import datetime

from rest_framework.authtoken.models import Token
from rest_framework.test import APITransactionTestCase
from rest_framework import status

from core.models import User

from cases.models import Case, CaseType, CaseWorkflowState, SubmissionType

from security.models import CaseRole

from workflow.models import WorkflowTemplate


class CaseTest(APITransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.submission_type = SubmissionType.objects.create(
            name="hello world", id=str(round(datetime.datetime.now().timestamp()))
        )
        self.workflow = WorkflowTemplate.objects.create(
            name="some dumb json", template={"key": "ASSIGN_TEAM"}
        )
        try:
            latest_case_type = CaseType.objects.last().id
        except AttributeError:
            latest_case_type = 0
        self.case_type = CaseType.objects.create(
            id=latest_case_type + 1,
            name="dumb and dumber",
            workflow=self.workflow,
        )
        try:
            latest_case_role = CaseRole.objects.last().id
        except AttributeError:
            latest_case_role = 0
        self.case_role = CaseRole.objects.create(
            name="king",
            id=latest_case_role + 1,
        )
        self.user = User.objects.create(
            name="Jack",
            email="jack@gov.uk",  # /PS-IGNORE
            password="super-secret-password1!",
        )
        token = Token.objects.create(user=self.user, key="super-secret-token1!")
        self.client.force_authenticate(user=self.user, token=token)

    def test_finds_all_cases(self):
        user2 = User.objects.create(
            name="jill",
            email="jill@gov.uk",  # /PS-IGNORE
            password="super-secret-password1!",
        )
        organisation, user2_case, submission = Case.objects.create_new_case(
            user2,
            case_type_id=self.case_type.id,
            role=self.case_role.id,
            contact_name="dumb king",
            organisation_name="dummy",
            case_name="dummies for a dummy",
            submission_type_id=self.submission_type.id,
        )
        organisation, my_case, submission = Case.objects.create_new_case(
            self.user,
            case_type_id=self.case_type.id,
            role=self.case_role.id,
            contact_name="dumb king",
            organisation_name="dummy",
            case_name="dummies for another dummy",
            submission_type_id=self.submission_type.id,
        )
        response = self.client.get("/api/v2/cases/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        ids = [each["id"] for each in response.data]
        assert str(user2_case.id) in ids
        assert str(my_case.id) in ids

    def test_finds_cases_open_to_user_for_registration_of_interest(self):
        Case.objects.create_new_case(
            self.user,
            case_type_id=self.case_type.id,
            role=self.case_role.id,
            contact_name="dumb king",
            organisation_name="dummy",
            case_name="dummies for a dummy",
            submission_type_id=self.submission_type.id,
        )
        organisation, roi_case, submission = Case.objects.create_new_case(
            self.user,
            case_type_id=self.case_type.id,
            role=self.case_role.id,
            contact_name="dumb king",
            organisation_name="dummy",
            case_name="dummies for another dummy",
            submission_type_id=self.submission_type.id,
        )
        roi_case.initiated_at = datetime.datetime.utcnow()
        roi_case.save()
        CaseWorkflowState.objects.create(
            case=roi_case, key="REGISTRATION_OF_INTEREST_TIMER", value=True
        )
        response = self.client.get("/api/v2/cases/?open_to_roi=True")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["name"] == "dummies for another dummy"
