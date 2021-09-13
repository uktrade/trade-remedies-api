from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time
from core.user_context import UserContext
from audit.models import Audit
from audit.utils import audit_log
from audit import AUDIT_TYPE_LOGIN
from cases.models import Case, Submission, SubmissionType, SubmissionDocument
from core.models import User
from documents.models import Document


class AuditTestMixin(object):
    def setup_test(self):
        self.user = User.objects.create(email="test@user.com", name="Joe Public")#PS-IGNORE
        self.caseworker = User.objects.create(email="case@worker.com", name="Case Worker")#PS-IGNORE
        self.unassisted_user_context = UserContext(self.user)
        self.assisted_user_context = UserContext(self.user, assisted_by=self.caseworker)
        self.unassisted_case = Case.objects.create(
            created_by=self.user, name="Untitled", user_context=self.unassisted_user_context
        )
        self.assisted_case = Case.objects.create(
            created_by=self.user, name="Untitled", user_context=self.assisted_user_context
        )


class AuditTest(TestCase, AuditTestMixin):

    def setUp(self):
        self.setup_test()

    def test_case_audit_creation(self):
        audit = Audit.objects.filter(case_id=self.unassisted_case.id, type="CREATE")
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0].case_id, self.unassisted_case.id)

    def test_case_change_unassisted_audit(self):
        """
        Test case edited by user (unassisted) generates the right audit message
        """
        self.unassisted_case.name = "Changed"
        self.unassisted_case.save()
        audits = Audit.objects.filter(case_id=self.unassisted_case.id)
        audit = Audit.objects.get(case_id=self.unassisted_case.id, type="UPDATE")
        self.assertEqual(len(audits), 2)
        self.assertEqual(audit.case_id, self.unassisted_case.id)
        self.assertEqual(audit.data["name"]["from"], "Untitled")
        self.assertEqual(audit.data["name"]["to"], "Changed")
        self.assertEqual(audit.created_by, self.user)
        self.assertIsNone(audit.assisted_by)

    def test_case_change_assisted_audit(self):
        """
        Test case edited by case worker on behalf of a user (assisted) generates
        the right audit message
        """
        self.assisted_case.name = "Changed"
        self.assisted_case.save()
        audits = Audit.objects.filter(case_id=self.assisted_case.id)
        audit = Audit.objects.get(case_id=self.assisted_case.id, type="UPDATE")
        self.assertEqual(len(audits), 2)
        self.assertEqual(audit.case_id, self.assisted_case.id)
        self.assertEqual(audit.data["name"]["from"], "Untitled")
        self.assertEqual(audit.data["name"]["to"], "Changed")
        self.assertEqual(audit.created_by, self.user)
        self.assertEqual(audit.assisted_by, self.caseworker)

    def test_submission_assisted(self):
        submission_type = SubmissionType.objects.get(name="Application")
        submission = Submission.objects.create(
            type=submission_type,
            case=self.assisted_case,
            created_by=self.user,
            user_context=self.assisted_user_context,
        )
        submission.review = True
        submission.save()
        audits = Audit.objects.filter(model_id=submission.id)
        audit = Audit.objects.get(model_id=submission.id, type="UPDATE")
        self.assertEqual(submission.modified_by, self.user)
        self.assertEqual(len(audits), 2)
        self.assertEqual(audit.case_id, self.assisted_case.id)
        self.assertEqual(audit.assisted_by_id, self.caseworker.id)
        self.assertIsNone(audit.data["review"]["from"])
        self.assertTrue(audit.data["review"]["to"])

    def test_submission_document_assisted(self):
        submission_type = SubmissionType.objects.get(name="Application")
        submission = Submission.objects.create(
            type=submission_type,
            case=self.assisted_case,
            created_by=self.user,
            user_context=self.assisted_user_context,
        )
        document = Document.objects.create(name="Test Document")
        submission_document = SubmissionDocument.objects.create(
            submission=submission, document=document, user_context=self.assisted_user_context
        )
        submission_document_id = submission_document.id
        submission_document.delete()
        audit = Audit.objects.get(model_id=submission_document_id, type="PURGE")
        self.assertEqual(audit.model_id, submission_document_id)

    def test_soft_delete(self):
        submission_type = SubmissionType.objects.get(name="Application")
        submission = Submission.objects.create(
            type=submission_type,
            case=self.assisted_case,
            created_by=self.user,
            user_context=self.assisted_user_context,
        )
        submission.review = True
        submission.save()
        submission_id = submission.id
        submission.delete()
        audit = Audit.objects.get(model_id=submission.id, type="DELETE")
        assert audit.model_id == submission_id


class AuditTasksTest(TestCase, AuditTestMixin):

    def setUp(self):
        self.setup_test()
        Audit.objects.all().delete()

    @freeze_time("2018-12-25 13:32:00")
    def test_custom_audit_log(self):
        audit_log(
            audit_type=AUDIT_TYPE_LOGIN,
            user=self.user,
            assisted_by=self.caseworker,
            case=self.assisted_case,
            model=self.unassisted_case,
            data={"a": "b"},
            milestone=True,
        )

        self.assertEqual(Audit.objects.count(), 1)
        audit = Audit.objects.first()
        self.assertEqual(audit.created_by, self.user)
        self.assertTrue(audit.milestone)
        self.assertIn("a", audit.data)
        self.assertEqual(audit.case_id, self.assisted_case.id)
        self.assertEqual(audit.get_model(), self.unassisted_case)
        self.assertEqual(audit.created_at, timezone.now())


class AuditModelHelpersTest(TestCase, AuditTestMixin):
    def setUp(self):
        self.setup_test()

    def test_row_values(self):
        audit = Audit.objects.first()
        row = audit.row_values()
        # Check some of the important values
        self.assertEqual(row[0], str(audit.id))
        self.assertEqual(row[1], audit.type)
        self.assertEqual(row[2], audit.created_at.strftime(settings.API_DATETIME_FORMAT))
        self.assertEqual(row[5], str(audit.case_id))
        self.assertEqual(row[6], str(audit.case))
        self.assertEqual(row[7], str(audit.model_id))

    def test_row_columns(self):
        audit = Audit.objects.first()
        expected = [
            "Audit ID", "Audit Type", "Created At", "Created By", "Assisted By",
            "Case Id", "Case", "Record Id", "Record Type", "Audit Content",
            "Change Data"
        ]
        self.assertEqual(audit.row_columns(), expected)

    def test_to_row(self):
        audit = Audit.objects.first()
        # Check some of the important values
        expected = [("Audit ID", str(audit.id)),
                    ("Audit Type", audit.type),
                    ("Created At", audit.created_at.strftime(settings.API_DATETIME_FORMAT)),
                    ("Case Id", str(audit.case_id)),
                    ("Case", str(audit.case)),
                    ("Record Id", str(audit.model_id)),
                    ]
        row = audit.to_row()
        self.assertEqual(row[0], expected[0])
        self.assertEqual(row[1], expected[1])
        self.assertEqual(row[2], expected[2])
        self.assertEqual(row[5], expected[3])
        self.assertEqual(row[6], expected[4])
        self.assertEqual(row[7], expected[5])

    def test_case_title(self):
        audit = Audit.objects.first()
        # Check case_title property is as expected
        self.assertEqual(audit.case_title, str(audit.case))

    def test_case_title_saved(self):
        Audit.objects.all().delete()
        case = Case.objects.create(created_by=self.user, name="Foobar")
        case_title = str(case)
        audit = Audit(type="CREATE", case_id=case.id)
        audit_id = audit.id
        # Unsaved, there should be no json field data
        assert not audit.data
        # But we should get a case title
        self.assertEqual(audit.case_title, case_title)
        # That auto-populates the json field
        assert audit.data.get("case_title")
        audit.save()
        # That we see in a retrieved model
        saved_audit = Audit.objects.filter(id=audit_id)[0]
        self.assertEqual(saved_audit.data["case_title"], case_title)
        self.assertEqual(saved_audit.case_title, case_title)

    def test_existing_data_preserved(self):
        Audit.objects.all().delete()
        # Create a case which elicits an audit log
        case = Case.objects.create(created_by=self.user, name="Foobar")
        assert case
        case_title = str(case)
        audit = Audit.objects.filter(created_by=self.user).first()
        assert audit
        # Clumsily update JSON field
        audit.data = {"my-data": 123}
        audit.save()
        audit = Audit.objects.filter(created_by=self.user).first()
        self.assertEqual(audit.data, {"my-data": 123, "case_title": case_title})
        # Update JSON field
        audit.data["more-data"] = "foobar"
        self.assertEqual(audit.case_title, case_title)
        # Prove JSON field preserved after case title property access
        self.assertEqual(audit.data,
                         {"my-data": 123,
                          "case_title": case_title,
                          "more-data": "foobar"}
                         )
