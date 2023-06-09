from django.test import override_settings
from v2_api_client.shared.logging import PRODUCTION_LOGGING, audit_logger

from config.test_bases import CaseSetupTestMixin
from test_functional import FunctionalTestBase


@override_settings(LOGGING=PRODUCTION_LOGGING)
class TestAuditLogger(CaseSetupTestMixin, FunctionalTestBase):
    def test_v2_audit_logging(self):
        """Tests that the correct logs are made when V2 Viewsets are accessed."""
        with self.assertLogs(audit_logger, level="INFO") as cm:
            response = self.client.get("/api/v2/cases/")
        log = cm.records[0]
        assert hasattr(log, "extra_details")
        assert log.extra_details["user"] == response.wsgi_request.user.id

        output = cm.output[0]
        assert "list operation" in output
        assert "API V2" in output

        with self.assertLogs(audit_logger, level="INFO") as cm:
            response = self.client.get(f"/api/v2/cases/{self.case_object.id}/")

        log = cm.records[0]
        assert hasattr(log, "extra_details")
        assert log.extra_details["user"] == response.wsgi_request.user.id
        assert log.extra_details["id"] == str(self.case_object.id)

        output = cm.output[0]
        assert "retrieve operation" in output

    def test_group_addition_audit_logging(self):
        """Tests that the correct logs are made when a user is added to a group."""
        self.user.groups.clear()
        with self.assertLogs(audit_logger, level="INFO") as cm:
            self.user.groups.add(self.owner_group)

        record = cm.records[0]
        assert hasattr(record, "extra_details")
        assert record.extra_details["user"] == self.user.id
        assert self.owner_group.name in record.extra_details["groups"]

        output = cm.output[0]
        assert "added to group" in output

    def test_group_addition_audit_logging_2(self):
        """Tests that the correct logs are made when a user is
        added to a group via the group interface."""
        self.user.groups.clear()
        with self.assertLogs(audit_logger, level="INFO") as cm:
            self.owner_group.user_set.add(self.user)

        record = cm.records[0]
        assert hasattr(record, "extra_details")
        assert record.extra_details["users"] == [
            self.user.id,
        ]
        assert self.owner_group.name in record.extra_details["group"]

        output = cm.output[0]
        assert "added to group" in output
