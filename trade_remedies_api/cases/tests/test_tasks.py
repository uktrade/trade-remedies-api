from datetime import datetime

from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from cases.models import CaseWorkflowState, TimeGateStatus
from cases.tasks import process_timegate_actions
from cases.tests.test_case import CaseTestMixin, get_case_fixtures


class ProcessTimeGateActionsTest(TestCase, CaseTestMixin):
    fixtures = get_case_fixtures()

    def setUp(self):
        self.setup_test()
        self.workflow_state, __ = CaseWorkflowState.objects.set_value(
            self.case, "PROV_FACTS_HEARINGS_TIMER", None, datetime(2019, 1, 10)
        )
        self.timegate_status = TimeGateStatus.objects.create(workflow_state=self.workflow_state)

    @freeze_time("2019-01-10 10:00:00")
    def test_run(self):
        process_timegate_actions()

        self.case.refresh_from_db()
        self.assertEqual(
            self.case.stage.key, "STATEMENT_OF_ESSENTIAL_FACTS_HEARING_REQUESTS_CLOSED"
        )
        updated_status = TimeGateStatus.objects.get(workflow_state=self.workflow_state)
        self.assertEqual(updated_status.ack_at, timezone.now())
