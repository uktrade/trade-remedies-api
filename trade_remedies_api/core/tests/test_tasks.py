from unittest.mock import patch, Mock

from django.test import TestCase
from notifications_python_client.errors import HTTPError

from audit import AUDIT_TYPE_NOTIFY, AUDIT_TYPE_EVENT
from audit.models import Audit
from cases.models import Case
from core.tasks import send_mail, SEND_MAIL_MAX_RETRIES, SEND_MAIL_COUNTDOWN
from core.user_context import UserContext
from core.models import User


notify_response = {
    "id": "740e5834-3a29-46b4-9a6f-16142fde533a",
    "reference": "STRING",
    "content": {"body": "MESSAGE TEXT", "from_number": "SENDER"},
    "uri": (
        "https://api.notifications.service.gov.uk/v2/notifications/"
        "740e5834-3a29-46b4-9a6f-16142fde533a"
    ),
    "template": {
        "id": "f33517ff-2a88-4f6e-b855-c550268ce08a",
        "version": 1,
        "uri": (
            "https://api.notifications.service.gov.uk/v2/template/"
            "ceb50d92-100d-4b8b-b559-14fa3b091cd"
        ),
    },
}


def create_error_response(message, status_code=400):
    response = Mock(status_code=status_code)
    response.json.return_value = {"errors": [{"message": message}]}
    return HTTPError(response=response)


class SendMailTest(TestCase):
    fixtures = ["submission_types.json"]

    def setUp(self):
        self.user = User.objects.create(email="test@user.com", name="Joe Public")
        self.user_context = UserContext(self.user)
        self.case = Case.objects.create(
            created_by=self.user, name="Untitled", user_context=self.user_context
        )
        Audit.objects.all().delete()
        self.email = "test@example.com"
        self.context = {"a": "b"}
        self.template_id = "my-template-1"
        self.reference = None
        self.audit_kwargs = {
            "audit_type": AUDIT_TYPE_EVENT,
            "user": self.user,
            "case": self.case,
            "model": self.case,
            "data": {"k-1": "v-1"},
        }

    @patch("core.tasks.sync_send_mail")
    def test_task(self, sync_send):
        sync_send.return_value = notify_response
        send_mail(self.email, self.context, self.template_id, audit_kwargs=self.audit_kwargs)
        sync_send.assert_called_once_with(
            self.email, self.context, self.template_id, self.reference
        )
        self.assertEqual(Audit.objects.all().count(), 1)
        audit = Audit.objects.first()
        self.assertEqual(audit.type, AUDIT_TYPE_EVENT)
        self.assertEqual(audit.created_by, self.user)
        self.assertEqual(audit.data["k-1"], "v-1")
        self.assertEqual(audit.data["send_report"], notify_response)

    @patch("core.tasks.sync_send_mail")
    def test_task_with_default_audit_type(self, sync_send):
        sync_send.return_value = notify_response
        audit_kwargs = self.audit_kwargs.copy()
        del audit_kwargs["audit_type"]
        send_mail(self.email, self.context, self.template_id, audit_kwargs=audit_kwargs)

        audit = Audit.objects.first()
        self.assertEqual(audit.type, AUDIT_TYPE_NOTIFY)

    @patch("core.tasks.sync_send_mail")
    def test_task_with_non_retryable_error(self, sync_send):
        sync_send.side_effect = create_error_response(message="BadRequest")
        send_mail(self.email, self.context, self.template_id, audit_kwargs=self.audit_kwargs)

        sync_send.assert_called_once_with(
            self.email, self.context, self.template_id, self.reference
        )
        self.assertEqual(Audit.objects.all().count(), 1)
        audit = Audit.objects.first()
        self.assertEqual(audit.type, AUDIT_TYPE_EVENT)
        self.assertEqual(audit.created_by, self.user)
        self.assertEqual(
            audit.data,
            {
                "case_title": str(self.case),
                "k-1": "v-1",
                "send_report": {
                    "email": self.email,
                    "error": ["BadRequest"],
                    "template_id": self.template_id,
                    "values": {"a": "b"},
                },
            },
        )

    @patch("celery.app.task.Task.retry")
    @patch("core.tasks.sync_send_mail")
    def test_task_with_retryable_error(self, sync_send, retry):
        error = create_error_response(message="ServerError", status_code=500)
        sync_send.side_effect = error
        send_mail(self.email, self.context, self.template_id, audit_kwargs=self.audit_kwargs)

        retry.assert_called_once_with(
            countdown=SEND_MAIL_COUNTDOWN, max_retries=SEND_MAIL_MAX_RETRIES, exc=error
        )
        self.assertEqual(sync_send.call_count, 1)
        self.assertEqual(Audit.objects.all().count(), 1)
