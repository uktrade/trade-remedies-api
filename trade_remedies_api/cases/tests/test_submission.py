from datetime import datetime

from django.test import TestCase
from freezegun import freeze_time

from cases.models import CaseWorkflowState, SubmissionType, Submission
from cases.tests.test_case import CaseTestMixin, get_case_fixtures

from cases.constants import DIRECTION_BOTH, DIRECTION_PUBLIC_TO_TRA, SUBMISSION_TYPE_HEARING_REQUEST


PASSWORD = "A7Hhfa!jfaw@f"


class SubmissionTypeTest(TestCase, CaseTestMixin):
    fixtures = get_case_fixtures("submission_types.json")

    def setUp(self):
        self.setup_test()
        self.hearing_request_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_HEARING_REQUEST)

    @freeze_time("2019-01-10 10:00:00")
    def test_get_available_submission_types_for_case(self):
        direction_kwargs = {"direction__in": [DIRECTION_BOTH, DIRECTION_PUBLIC_TO_TRA]}

        test_data = [
            ("SOME_KEY", None, False),
            ("PROV_FACTS_HEARINGS_TIMER", datetime(2019, 1, 9), False),
            ("PROV_FACTS_HEARINGS_TIMER", datetime(2019, 1, 11), True),
            ("PROV_FACTS_HEARINGS_TIMER", None, True),
        ]

        for key, due_date, contains in test_data:
            with self.subTest(key=key, due_date=due_date, contains=contains):
                workflow_state, __ = CaseWorkflowState.objects.set_value(
                    self.case, key, "", due_date
                )
                results = SubmissionType.objects.get_available_submission_types_for_case(
                    self.case, direction_kwargs
                )
                if contains:
                    self.assertEqual(results.count(), 1)
                    self.assertEqual(self.hearing_request_type, results[0])
                else:
                    self.assertEqual(results.count(), 0)


class SubmissionTest(TestCase, CaseTestMixin):
    fixtures = get_case_fixtures("submission_types.json")

    def setUp(self):
        self.setup_test()
        self.hearing_request_type = SubmissionType.objects.get(id=SUBMISSION_TYPE_HEARING_REQUEST)

    def test_create_without_window_based_due_date(self):
        submission = Submission.objects.create(
            name=self.hearing_request_type.name,
            type=self.hearing_request_type,
            status=self.hearing_request_type.default_status,
            case=self.case,
            organisation=self.organisation,
            created_by=self.user_owner,
        )

        self.assertIsNone(submission.due_at)
