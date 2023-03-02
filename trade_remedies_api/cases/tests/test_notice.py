import datetime

from django.test import TestCase

from cases.models import CaseType, Notice
from cases.tests.test_case import CaseTestMixin, get_case_fixtures
from core.models import User


class CaseTest(TestCase, CaseTestMixin):
    fixtures = get_case_fixtures()

    def setUp(self):
        self.now = datetime.datetime.now().date()
        self.user_owner = User.objects.create_user(
            name="org owner",  # /PS-IGNORE
            email="owner@test.com",  # /PS-IGNORE
            password="FSHJ3J472!£@3Fsdf",  # /PS-IGNORE
            assign_default_groups=False,
        )
        self.notice = Notice.objects.create(
            name="notice 1",
            reference="reference 1",
            case_type=CaseType.objects.get(acronym="AD"),
            published_at=self.now - datetime.timedelta(weeks=60),
            terminated_at=self.now + datetime.timedelta(weeks=60),
        )
        self.notice_expected_type_acronyms = {
            "IR",
            "SC",
            "ER",
            "AR",
            "CR",
            "NE",
            "SA",
            "RI",
            "SE",
            "SS",
            "BU",
            "TQ",
            "CE",
            "SN",
        }

    def test_correct_review_types(self):
        available_review_types = self.notice.available_case_review_types()
        self.assertEqual(len(available_review_types), len(self.notice_expected_type_acronyms))
        available_review_types = set([each["acronym"] for each in available_review_types])
        self.assertEqual(available_review_types, self.notice_expected_type_acronyms)

    def test_correct_review_types_termination_change_1(self):
        """Now we change the termination_at value of the Notice object to 6 weeks from now,
        this should NOT change the status of these review types to unavailable. This is
        because all review casetype expiry limits have been removed.
        """
        """available_review_types = self.notice.available_case_review_types()
        for available_review in available_review_types:
            # casetype review commencement/start limits have been removed
            self.assertEqual(available_review["dates"]["status"], "before_start")"""

        # Now we change the terminated_at value to 6 weeks from now
        self.notice.terminated_at = self.now + datetime.timedelta(weeks=6)
        self.notice.save()
        self.notice.refresh_from_db()

        available_review_types = self.notice.available_case_review_types()
        for available_review in available_review_types:
            if available_review["acronym"] not in ["RI", "CE", "CR"]:
                # review casetype end limits have been removed
                self.assertEqual(available_review["dates"]["status"], "ok")

    def test_correct_review_types_termination_change_2(self):
        """Now we change the termination_at value of the Notice object to 15 weeks from now,
        this should NOT change the status of these review types to unavailable. This is
        because all review catetype expiry limits have been removed.
        """
        self.notice.terminated_at = self.now + datetime.timedelta(weeks=15)
        self.notice.save()
        self.notice.refresh_from_db()
        available_review_types = self.notice.available_case_review_types()
        for available_review in available_review_types:
            # The Interim Review type should no longer be available as the measures are ending soon
            if available_review["acronym"] == "IR":
                self.assertEqual(available_review["dates"]["status"], "after_end")

            # The Scope Review type should be available as it's not 3 months till measure expiry
            if available_review["acronym"] == "SC":
                self.assertEqual(available_review["dates"]["status"], "ok")

    def test_correct_review_types_sf(self):
        """Tests that when the case_type of the Notice is changed, the review types should not."""
        previous_available_review_types = self.notice.available_case_review_types()
        self.notice.case_type = CaseType.objects.get(
            acronym="SF"
        )  # Change to safeguarding investigation
        self.notice.save()
        available_review_types = self.notice.available_case_review_types()

        self.assertEqual(previous_available_review_types, available_review_types)
