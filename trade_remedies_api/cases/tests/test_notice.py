import datetime

from django.test import TestCase

from cases.models import (
    CaseType,
    Notice
)
from cases.tests.test_case import get_case_fixtures, CaseTestMixin
from core.models import User


class CaseTest(TestCase, CaseTestMixin):
    fixtures = get_case_fixtures()

    def setUp(self):
        self.now = datetime.datetime.now().date()
        self.user_owner = User.objects.create_user(
            name="org owner", email="owner@test.com", password='FSHJ3J472!£@3Fsdf', assign_default_groups=False
            # /PS-IGNORE
        )
        self.notice = Notice.objects.create(
            name='notice 1',
            reference='reference 1',
            case_type=CaseType.objects.get(acronym='AD'),
            published_at=self.now - datetime.timedelta(weeks=60),
            terminated_at=self.now + datetime.timedelta(weeks=60)
        )

    def test_correct_review_types(self):
        available_review_type = self.notice.available_case_review_types()
        self.assertEqual(len(available_review_type), 9)  # Only 8 review types should be available for an AD case
        self.assertEqual(
            available_review_type[0]['name'],
            'Interim review'
        )  # Interim review should be the first result

    def test_correct_review_types_termination_change_1(self):
        """Now we change the termination_at value of the Notice object to 6 weeks from now,
        this should change the status of all of these review types of unavailable.
        """
        available_review_type = self.notice.available_case_review_types()
        self.assertEqual(
            available_review_type[0]['dates']['status'],
            'ok'
        )
        self.notice.terminated_at = self.now + datetime.timedelta(weeks=6)
        self.notice.save()
        self.notice.refresh_from_db()
        available_review_type = self.notice.available_case_review_types()
        self.assertEqual(
            available_review_type[0]['dates']['status'],
            'after_end'  # The review type should no longer be available as the measures are ending very soon
        )

    def test_correct_review_types_termination_change_2(self):
        """Now we change the termination_at value of the Notice object to 15 weeks from now,
        this should change the status of SOME of these review types of unavailable.
        """
        available_review_type = self.notice.available_case_review_types()
        self.assertEqual(
            available_review_type[0]['dates']['status'],
            'ok'
        )
        self.notice.terminated_at = self.now + datetime.timedelta(weeks=15)
        self.notice.save()
        self.notice.refresh_from_db()
        available_review_type = self.notice.available_case_review_types()
        self.assertEqual(
            available_review_type[0]['dates']['status'],
            'after_end'  # The Interim Review type should no longer be available as the measures are ending soon
        )
        self.assertEqual(
            available_review_type[1]['dates']['status'],
            'ok'  # The Scope Review type should still be available as it's not 3 months till measure expiry
        )

    def test_correct_review_types_sf(self):
        """Tests that when the case_type of the Notice is changed, the review types also do.
        """
        self.notice.case_type = CaseType.objects.get(acronym='SF')  # Change to safeguarding investigation
        self.notice.terminated_at = self.now + datetime.timedelta(weeks=104)  # Change to expire > 18 months from now
        self.notice.save()
        available_review_type = self.notice.available_case_review_types()
        self.assertEqual(len(available_review_type), 3)  # Only 3 review types should be available for a SF notice
        review_types_extracted = [each['acronym'] for each in available_review_type]
        self.assertIn('RI', review_types_extracted)
        self.assertIn('SE', review_types_extracted)
        self.assertIn('SS', review_types_extracted)
