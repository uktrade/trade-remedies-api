from django.test import TestCase

from cases.models import CaseWorkflow
from cases.tests.test_case import CaseTestMixin, get_case_fixtures
from workflow.models import Workflow


class OutcomesTests(TestCase, CaseTestMixin):
    fixtures = get_case_fixtures()  # 'workflow_template_anti_dumping.json')

    def setUp(self):
        self.setup_test()
        self.workflow = Workflow({"root": [{"key": "MY_GROUP", "children": []}]})

    def setup_workflow(self, children):
        self.workflow["root"][0]["children"] = children
        CaseWorkflow.objects.filter(case=self.case).update(workflow=self.workflow)
        self.case.refresh_from_db()

    def setup_case_change_task_attributes(self):
        outcome_spec = [
            {
                "spec": [{"always": {"value": {"MY_KEY": {"active": False, "required": True}},}}],
                "type": "change_task_attributes",
            }
        ]

        task = {
            "key": "MY_KEY",
            "response_type": {"key": "YESNO"},
            "outcome_spec": outcome_spec,
            "active": True,
            "required": False,
            "value": "yes",
        }
        self.setup_workflow([task])

    def test_change_task_attributes(self):
        self.setup_case_change_task_attributes()

        self.workflow.evaluate_outcome("MY_KEY", case=self.case)

        self.assertFalse(self.case.workflow.as_workflow().get_node("MY_KEY")["active"])
        self.assertTrue(self.case.workflow.as_workflow().get_node("MY_KEY")["required"])
