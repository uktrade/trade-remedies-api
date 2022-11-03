from unittest import skip
from unittest.mock import patch
from urllib.parse import urlencode
from titlecase import titlecase
from rest_framework.test import APITestCase, APIClient, APIRequestFactory
from rest_framework import status
from django.contrib.auth.models import Group
from core.models import User, SystemParameter
from core.notifier import notify_contact_email, notify_footer
from core.utils import public_login_url
from organisations.models import Organisation
from cases.models import Case, CaseType, SubmissionType, Submission, CaseWorkflow
from cases.services.api import CasesAPIView
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_TRA_ADMINISTRATOR,
    SECURITY_GROUP_TRA_INVESTIGATOR,
    ROLE_APPLICANT,
)
from cases.tests.test_case import get_case_fixtures, load_system_params

PASSWORD = "A7Hhfa!jfaw@f"


class APISetUpMixin(object):
    def setup_test(self):
        """
        Organisation has one owner, and two standard users.
        Organisation is applicant of a case
        User 1 is assigned access to the case, user 2 is not.
        A third user is not part of the organisation
        """
        self.factory = APIRequestFactory()
        self.client = APIClient()
        self.view = CasesAPIView.as_view()
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        Group.objects.create(name=SECURITY_GROUP_TRA_ADMINISTRATOR)
        Group.objects.create(name=SECURITY_GROUP_TRA_INVESTIGATOR)
        # Create organisation
        self.organisation = Organisation.objects.create(name="Test Org")
        # create users:
        # two standard users, one owner, and one who will not be part of the org
        self.user_1 = User.objects.create_user(
            name="org user",
            email="standard@gov.uk",  # /PS-IGNORE
            password=PASSWORD,
            assign_default_groups=False,
            organisation=self.organisation,
        )
        self.user_2 = User.objects.create_user(
            name="org user",
            email="standard2@gov.uk",  # /PS-IGNORE
            password=PASSWORD,
            assign_default_groups=False,
            organisation=self.organisation,
        )
        self.user_owner = User.objects.create_user(
            name="org owner",
            email="owner@gov.uk",  # /PS-IGNORE
            password=PASSWORD,
            assign_default_groups=False,
            organisation=self.organisation,
        )
        self.user_denied = User.objects.create_user(
            name="user denied",
            email="invalid@gov.uk",  # /PS-IGNORE
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.investigator = User.objects.create_user(
            name="tra user",
            email="trainvestigator@gov.uk",  # /PS-IGNORE
            password=PASSWORD,
            groups=[SECURITY_GROUP_TRA_INVESTIGATOR],
        )

        self.case_type = CaseType.objects.get(acronym="AD")
        self.case = Case.objects.create(
            name="Test Case", created_by=self.user_owner, type=self.case_type
        )
        CaseWorkflow.objects.snapshot_from_template(self.case, self.case.type.workflow)
        self.organisation.assign_user(self.user_owner, SECURITY_GROUP_ORGANISATION_OWNER)
        self.organisation.assign_user(self.user_1, SECURITY_GROUP_ORGANISATION_USER)
        self.organisation.assign_user(self.user_2, SECURITY_GROUP_ORGANISATION_USER)
        self.organisation.assign_case(self.case, ROLE_APPLICANT)
        # user 1 is assigned access directly. user 2 is not
        self.case.assign_organisation_user(self.user_1, self.organisation)

    def post_form(self, url, payload):
        return self.client.post(
            url, urlencode(payload), content_type="application/x-www-form-urlencoded"
        )


class CaseAPITest(APITestCase, APISetUpMixin):
    fixtures = get_case_fixtures()

    def setUp(self):
        self.setup_test()

    @skip("Fix for updated security model")
    def test_user_access_denied(self):
        self.client.force_authenticate(user=self.user_denied, token=self.user_denied.auth_token)
        response = self.client.get(f"/api/v1/cases/organisation/{self.organisation.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_access_allowed(self):
        self.client.force_authenticate(user=self.user_1, token=self.user_1.auth_token)
        response = self.client.get(f"/api/v1/cases/{self.case.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_cases_assigned_user(self):
        self.client.force_authenticate(user=self.user_1, token=self.user_1.auth_token)
        response = self.client.get(f"/api/v1/cases/{self.case.id}/")
        response_data = response.json()
        self.assertEqual(response_data["response"]["result"]["id"], str(self.case.id))

    def test_get_cases_owner_user(self):
        self.client.force_authenticate(user=self.user_owner, token=self.user_1.auth_token)
        response = self.client.get(f"/api/v1/cases/{self.case.id}/")
        response_data = response.json()
        self.assertEqual(response_data["response"]["result"]["id"], str(self.case.id))

    @skip("Fix for updated security model")
    def test_get_cases_unassigned_user(self):
        self.client.force_authenticate(user=self.user_2, token=self.user_2.auth_token)
        response = self.client.get(f"/api/v1/cases/{self.case.id}/")
        response_data = response.json()
        self.assertEqual(len(response_data["response"]["results"]), 0)


class SubmissionAPITest(APITestCase, APISetUpMixin):
    fixtures = get_case_fixtures(
        "submission_document_types.json",
    )

    def setUp(self):
        self.setup_test()

    def test_create_submission(self):
        payload = {
            "submission_type": "General",
            "submission_status_id": 7,
            "name": "General(name)",
        }
        self.client.force_authenticate(user=self.user_1, token=self.user_1.auth_token)
        url = f"/api/v1/cases/{self.case.id}/organisation/" f"{self.organisation.id}/submissions/"

        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response_data = response.json()
        self.assertEqual(response_data["response"]["result"]["submission"]["name"], "General(name)")
        self.assertEqual(response_data["response"]["result"]["submission"]["status"]["id"], 7)
        self.assertEqual(
            response_data["response"]["result"]["submission"]["type"]["name"], "General"
        )

    def test_get_all_organisation_submissions(self):
        pass

    def test_get_case_submissions(self):
        pass

    def test_access_denied_get_submissions(self):
        pass


class SubmissionStatusAPITest(APITestCase, APISetUpMixin):
    fixtures = get_case_fixtures()

    def setUp(self):
        self.setup_test()
        load_system_params()
        self.submission_type = SubmissionType.objects.get(name="Questionnaire")
        self.submission = Submission.objects.create(
            type=self.submission_type,
            case=self.case,
            contact=self.user_1.contact,
            organisation=self.organisation,
            created_by=self.user_1,
        )
        self.url = (
            f"/api/v1/cases/{self.case.id}/organisation/{self.organisation.id}/"
            f"submission/{self.submission.id}/status/"
        )

    @patch("core.notifier.NotificationsAPIClient")
    def test_create_submission(self, notifier_client):
        payload = {
            "submission_type": "Questionnaire",
            "submission_status_id": 6,
            "status_context": "sent",
        }
        self.client.force_authenticate(user=self.user_1, token=self.user_1.auth_token)
        response = self.post_form(self.url, payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(notifier_client().send_email_notification.call_count, 0)
        response_data = response.data["response"]
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["result"]["submission"]["id"], str(self.submission.id))
        self.assertEqual(response_data["result"]["submission"]["type"]["name"], "Questionnaire")

    @patch("core.notifier.NotificationsAPIClient")
    def test_create_submission_with_notification(self, notifier_client):
        self.submission_type = SubmissionType.objects.get(name="General")
        self.submission.type = self.submission_type
        self.submission.save()
        payload = {
            "submission_type": "General",
            "submission_status_id": 7,
            "status_context": "received",
        }
        notifier_client().send_email_notification.return_value = {}
        self.client.force_authenticate(user=self.user_1, token=self.user_1.auth_token)
        response = self.post_form(self.url, payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Build footer
        email = notify_contact_email(self.case.reference)
        footer = notify_footer(email=email)
        notify_data = {
            "company": self.organisation.name,
            "case_name": self.case.name,
            "case_title": self.case.name,
            "case_number": self.case.reference,
            "investigation_type": self.case.type.name,
            "dumped_or_subsidised": self.case.dumped_or_subsidised(),
            "product": "",
            "full_name": self.user_1.contact.name.strip(),
            "country": "N/A",
            "organisation_name": titlecase(self.organisation.name),
            "notice_url": self.submission.url or "N/A",  # TODO: Remove
            "notice_of_initiation_url": self.submission.url or "N/A",
            "login_url": public_login_url(),
            "submission_type": "General",
            "company_name": titlecase(self.submission.organisation.name)
            if self.submission.organisation
            else "",
            "deadline": "",
            "footer": footer,
            "email": email,
            "guidance_url": SystemParameter.get("LINK_HELP_BOX_GUIDANCE"),
        }
        notifier_client().send_email_notification.assert_called_once_with(
            email_address=self.user_1.email,
            personalisation=notify_data,
            reference=None,
            template_id="d6fb3018-2338-40c9-aa6d-f1195f5f65de",  # /PS-IGNORE
        )
        response_data = response.data["response"]
        self.assertTrue(response_data["success"])
        self.assertEqual(response_data["result"]["submission"]["id"], str(self.submission.id))
        self.assertEqual(response_data["result"]["submission"]["type"]["name"], "General")
