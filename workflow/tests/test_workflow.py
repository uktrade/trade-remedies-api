from django.test import TestCase
from workflow.models import WorkflowTemplate


class WorkflowTest(TestCase):
    fixtures = [
        "workflow_template_anti_dumping.json",
    ]

    def setUp(self):
        """

        """
        self.template = WorkflowTemplate.objects.first()

    def test_key_precedes(self):
        self.assertTrue(
            self.template.workflow.key_precedes("ASSIGN_MANAGER", "REVIEW_DRAFT_CONFIRM")
        )

    def test_key_precedes_when_false(self):
        self.assertFalse(
            self.template.workflow.key_precedes("REVIEW_DRAFT_CONFIRM", "ASSIGN_MANAGER")
        )
