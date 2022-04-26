import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group
from django.test import TestCase

from cases.models import (Case, CaseStage, CaseType, CaseWorkflow)
from core.models import SystemParameter, User
from organisations.models import Organisation
from security.constants import (ROLE_APPLICANT, SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER,
                                SECURITY_GROUP_TRA_ADMINISTRATOR, SECURITY_GROUP_TRA_INVESTIGATOR)

PASSWORD = "A7Hhfa!jfaw@f"


def get_case_fixtures(*extra):
    fixtures = [
        "tra_organisations.json",
        "actions.json",
        "case_types.json",
        "case_stages.json",
        "roles.json",
        "workflow_template_anti_dumping.json",
        "workflow_template_trans_anti_subsidy.json",
        "workflow_template_safeguards.json",
        "workflow_template_trans_anti_dumping.json",
        "workflow_template_trans_safeguards.json",
        "workflow_template_anti_subsidy.json",
    ]
    if extra:
        fixtures.extend(extra)
    return fixtures


def load_system_params():
    with open(os.path.join(Path(settings.BASE_DIR).parent.absolute(), "core/system/parameters.json")) as json_data:
        objects = json.loads(str(json_data.read()))
    return SystemParameter.load_parameters(objects)


class CaseTestMixin(object):
    def setup_test(self):
        """
        Organisation has one owner, and two standard users.
        Organisation is applicant of a case
        User 1 is assigned access to the case, user 2 is not.
        A third user is not part of the organisation
        """
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        Group.objects.create(name=SECURITY_GROUP_TRA_ADMINISTRATOR)
        Group.objects.create(name=SECURITY_GROUP_TRA_INVESTIGATOR)
        # create users:
        # two standard users, one owner, and one who will not be part of the org
        self.user_owner = User.objects.create_user(
            name="org owner", email="owner@test.com", password=PASSWORD, assign_default_groups=False  # /PS-IGNORE
        )
        self.investigator = User.objects.create_user(
            name="tra user",
            email="trainvestigator@test.com",  # /PS-IGNORE
            password=PASSWORD,
            groups=[SECURITY_GROUP_TRA_INVESTIGATOR],
        )
        self.organisation = Organisation.objects.create(name="Test Org")
        self.case_type = CaseType.objects.get(acronym="AD")
        self.case = Case.objects.create(
            name="Test Case", created_by=self.user_owner, type=self.case_type
        )
        CaseWorkflow.objects.snapshot_from_template(self.case, self.case.type.workflow)
        self.organisation.assign_user(self.user_owner, SECURITY_GROUP_ORGANISATION_OWNER)
        self.organisation.assign_case(self.case, ROLE_APPLICANT)
        # user 1 is assigned access directly. user 2 is not
        self.case.assign_organisation_user(self.user_owner, self.organisation)


class CaseTest(TestCase, CaseTestMixin):
    fixtures = get_case_fixtures()

    def setUp(self):
        self.setup_test()

    def test_stage_transition(self):
        """
        Test that stage 1 can be set,
        stage 2 can be set,
        after stage 2 is set, stage 3 cannot be set.
        """
        stage_1 = CaseStage.objects.get(key="DRAFT_RECEIVED")
        stage_2 = CaseStage.objects.get(key="APPLICATION_RECEIVED")
        stage_3 = CaseStage.objects.get(key="DRAFT_REVIEW")
        _stage_1 = self.case.set_stage(stage_1)
        _stage_2 = self.case.set_stage(stage_2)
        _stage_3 = self.case.set_stage(stage_3)
        self.assertEqual(_stage_1, stage_1)
        self.assertEqual(_stage_2, stage_2)
        self.assertEqual(_stage_3, None)
        self.assertEqual(self.case.stage, stage_2)

    def test_stage_transition_ignore_flow(self):
        """
        Test that stage 1 can be set,
        stage 2 can be set, as ignoring flow
        """
        stage_1 = CaseStage.objects.get(key="APPLICATION_RECEIVED")
        stage_2 = CaseStage.objects.get(key="DRAFT_REVIEW")
        _stage_1 = self.case.set_stage(stage_1)
        _stage_2 = self.case.set_stage(stage_2, ignore_flow=True)
        self.assertEqual(_stage_1, stage_1)
        self.assertEqual(_stage_2, stage_2)
        self.assertEqual(self.case.stage, stage_2)
