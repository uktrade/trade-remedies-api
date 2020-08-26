from django.test import TestCase
from core.models import User
from organisations.models import Organisation
from cases.models import Case
from django.contrib.auth.models import Group
from security.constants import (
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    SECURITY_GROUP_TRA_ADMINISTRATOR,
    ROLE_APPLICANT,
    ROLE_DOMESTIC_PRODUCER,
)

PASSWORD = "A7Hhfa!jfaw@f"


class SecurityTest(TestCase):
    fixtures = ["tra_organisations.json", "actions.json", "roles.json"]

    def setUp(self):
        """
        Setup Scenario, only direct users:
            5 users, 3 organisations and 2 cases

            Org A: User A1 (admin), User A2
            Org B: User B1 (admin), User B2
            Org C: User C1 (admin)

            Case X:
            - Org A (Applicant)
                - User A1, User A2 assigned
            - Org B (Domestic Producer)
                 - User B1, User B2 assigned

            Case Y:
            - Org B (Applicant)
                - User B1 but not User B2 assigned
            - Org C (Importer)
                 - User C1 assigned
        """
        Group.objects.create(name=SECURITY_GROUP_TRA_ADMINISTRATOR)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        # create users
        self.traUser = User.objects.create_user(
            name="tra user",
            email="adminuser@tra.gov",
            password=PASSWORD,
            assign_default_groups=False,
            groups=[SECURITY_GROUP_TRA_ADMINISTRATOR],
        )
        self.userA1 = User.objects.create_user(
            name="org owner",
            email="user1@test.com",
            password=PASSWORD,
            assign_default_groups=False,
            groups=[SECURITY_GROUP_ORGANISATION_OWNER],
        )
        self.userA2 = User.objects.create_user(
            name="org user",
            email="user2@test.com",
            password=PASSWORD,
            assign_default_groups=False,
            groups=[SECURITY_GROUP_ORGANISATION_USER],
        )
        self.userB1 = User.objects.create_user(
            name="org owner 2",
            email="user3@test.com",
            password=PASSWORD,
            assign_default_groups=False,
            groups=[SECURITY_GROUP_ORGANISATION_OWNER],
        )
        self.userB2 = User.objects.create_user(
            name="org user 2",
            email="user4@test.com",
            password=PASSWORD,
            assign_default_groups=False,
            groups=[SECURITY_GROUP_ORGANISATION_USER],
        )
        self.userC1 = User.objects.create_user(
            name="org owner 3",
            email="user5@test.com",
            password=PASSWORD,
            assign_default_groups=False,
            groups=[SECURITY_GROUP_ORGANISATION_OWNER],
        )
        # create organisations
        self.organisationA = Organisation.objects.create(name="Test Org A")
        self.organisationB = Organisation.objects.create(name="Test Org B")
        self.organisationC = Organisation.objects.create(name="Test Org C")
        # assign users to organisation
        self.organisationA.assign_user(self.userA1, SECURITY_GROUP_ORGANISATION_OWNER)
        self.organisationA.assign_user(self.userA2, SECURITY_GROUP_ORGANISATION_USER)
        self.organisationB.assign_user(self.userB1, SECURITY_GROUP_ORGANISATION_OWNER)
        self.organisationB.assign_user(self.userB2, SECURITY_GROUP_ORGANISATION_USER)
        self.organisationC.assign_user(self.userC1, SECURITY_GROUP_ORGANISATION_OWNER)
        # Create cases
        self.caseX = Case.objects.create(name="Test Case X")
        self.caseY = Case.objects.create(name="Test Case Y")
        # Assign cases to organisations and users
        # User->Case assignment is explicit and is set by TRA or Org. owner
        self.organisationA.assign_case(self.caseX, ROLE_APPLICANT)
        self.organisationB.assign_case(self.caseX, ROLE_DOMESTIC_PRODUCER)
        self.organisationB.assign_case(self.caseY, ROLE_APPLICANT)
        self.organisationC.assign_case(self.caseY, ROLE_DOMESTIC_PRODUCER)
        # user A1 (admin) is given access to caseX
        # user A2 (normal) is given access to caseX:
        self.caseX.assign_user(self.userA1, self.userA1, self.organisationA, relax_security=True)
        self.caseX.assign_user(self.userA2, self.traUser, self.organisationA)
        self.caseX.assign_user(self.userB1, self.userB1, self.organisationB, relax_security=True)
        self.caseX.assign_user(self.userB2, self.traUser, self.organisationB)
        self.caseY.assign_user(self.userB1, self.traUser, self.organisationB)
        self.caseY.assign_user(self.userC1, self.traUser, self.organisationC)

    def test_organisations_have_correct_roles_assigned(self):
        """
        Test organisations have their assigned role in their cases
        """
        assert self.caseX.has_organisation(self.organisationA, ROLE_APPLICANT)
        assert not self.caseX.has_organisation(self.organisationA, ROLE_DOMESTIC_PRODUCER)
        assert self.caseX.has_organisation(self.organisationB, ROLE_DOMESTIC_PRODUCER)
        assert not self.caseX.has_organisation(self.organisationB, ROLE_APPLICANT)
        assert not self.caseX.has_organisation(self.organisationC, ROLE_APPLICANT)
        assert not self.caseX.has_organisation(self.organisationC, ROLE_DOMESTIC_PRODUCER)

        assert not self.caseY.has_organisation(self.organisationA, ROLE_APPLICANT)
        assert not self.caseY.has_organisation(self.organisationA, ROLE_DOMESTIC_PRODUCER)
        assert self.caseY.has_organisation(self.organisationB, ROLE_APPLICANT)
        assert not self.caseY.has_organisation(self.organisationB, ROLE_DOMESTIC_PRODUCER)
        assert not self.caseY.has_organisation(self.organisationC, ROLE_APPLICANT)
        assert self.caseY.has_organisation(self.organisationC, ROLE_DOMESTIC_PRODUCER)

    def test_users_are_in_correct_organisations(self):
        """
        Test a user can view cases to which they have been assigned
        """
        assert self.userA1.userprofile.all_organisations == [self.organisationA]
        assert self.userA2.userprofile.all_organisations == [self.organisationA]
        assert self.userB1.userprofile.all_organisations == [self.organisationB]
        assert self.userB2.userprofile.all_organisations == [self.organisationB]
        assert self.userC1.userprofile.all_organisations == [self.organisationC]

    def _test_users_can_see_cases(self):
        """
        Test a user can view cases to which they have been assigned
        """
        # test either this way or with a .get_cases() method?

        # we need to specify a user and an organisation because users can have multiple orgs
        assert self.userA1.can_do("VIEW_CASE", self.organisationA, self.caseX)
        assert not self.userA1.can_do("VIEW_CASE", self.organisationB, self.caseX)
        # should the below fail or raise an exception? org C isn't in case X!
        assert not self.userA1.can_do("VIEW_CASE", self.organisationC, self.caseX)
        assert not self.userA1.can_do("VIEW_CASE", self.organisationA, self.caseY)
        assert not self.userA1.can_do("VIEW_CASE", self.organisationB, self.caseY)
        assert not self.userA1.can_do("VIEW_CASE", self.organisationC, self.caseY)

    def _test_users_can_upload_docs_to_their_own_cases(self):
        """
        Test that a user can upload documents to a given case on behalf of a given org
        """
        assert self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert not self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        # org B is in case Y, but user B2 isn't enabled for case Y
        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert not self.userC1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert not self.userC1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userC1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userC1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert not self.userC1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert self.userC1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)


class AgentSecurityTest(TestCase):
    """
    Security scenarios involving agents (consultants and lawyers)
    """

    fixtures = ["actions.json", "roles.json"]

    def setUp(self):
        """
        Setup Scenario including agent users:
            5 normal users, 2 "lawyer users", 3 organisations and 2 cases

            Orgs have appointed lawyers to work on their behalf.

            Org A: User A1 (admin), User A2, User L1
            Org B: User B1 (admin), User B2, User L1, User L2
            Org C: User L2 (admin)

            Case X:
            - Org A (Applicant)
                - User A1, User A2, User L1
            - Org B (Respondent)
                 - User B1, User B2, User L1, User L2

            Case Y:
            - Org B (Applicant)
                - User B1, User L1 but not User B2 or User L2
            - Org C (Respondent)
                - User L2
        """
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_OWNER)
        Group.objects.create(name=SECURITY_GROUP_ORGANISATION_USER)
        # create users
        self.userA1 = User.objects.create_user(
            name="user one",
            email="user1@organisationA.com",
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.userA2 = User.objects.create_user(
            name="user two",
            email="user2@organisationA.com",
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.userB1 = User.objects.create_user(
            name="user three",
            email="user3@organisationB.com",
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.userB2 = User.objects.create_user(
            name="user four",
            email="user4@organisationB.com",
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.userL1 = User.objects.create_user(
            name="user lawyer",
            email="lawyer1@lawyer1.com",
            password=PASSWORD,
            assign_default_groups=False,
        )
        self.userL2 = User.objects.create_user(
            name="user lawyer 2",
            email="lawyer2@lawyer2.com",
            password=PASSWORD,
            assign_default_groups=False,
        )
        # create organisations
        self.organisationA = Organisation.objects.create(name="Test Org A")
        self.organisationB = Organisation.objects.create(name="Test Org B")
        self.organisationC = Organisation.objects.create(name="Test Org C")
        # assign users to organisation
        self.organisationA.assign_user(self.userA1, SECURITY_GROUP_ORGANISATION_OWNER)
        self.organisationA.assign_user(self.userA2, SECURITY_GROUP_ORGANISATION_USER)
        self.organisationA.assign_user(self.userL1, SECURITY_GROUP_ORGANISATION_USER)

        self.organisationB.assign_user(self.userB1, SECURITY_GROUP_ORGANISATION_OWNER)
        self.organisationB.assign_user(self.userB2, SECURITY_GROUP_ORGANISATION_USER)
        self.organisationB.assign_user(self.userL1, SECURITY_GROUP_ORGANISATION_USER)
        self.organisationB.assign_user(self.userL2, SECURITY_GROUP_ORGANISATION_USER)

        self.organisationC.assign_user(self.userL2, SECURITY_GROUP_ORGANISATION_OWNER)

        # Create cases
        self.caseX = Case.objects.create(name="Test Case X")
        self.caseY = Case.objects.create(name="Test Case Y")
        # Assign cases to organisations and users
        self.organisationA.assign_case(self.caseX, ROLE_APPLICANT)
        # user A1 (admin) has implied access to caseX because they're admin of org A
        # user A2 (normal) is given access to caseX:
        self.caseX.assign_organisation_user(self.userA2, self.organisationA)
        self.caseX.assign_organisation_user(self.userL1, self.organisationA)

        self.organisationB.assign_case(self.caseX, ROLE_DOMESTIC_PRODUCER)
        # user B1 (admin) is redundantly given access to caseX but has implied access to caseY:
        self.caseX.assign_organisation_user(self.userB1, self.organisationB)
        # user B2 (normal) is given access to caseX but not caseY:
        self.caseX.assign_organisation_user(self.userB2, self.organisationB)
        self.caseX.assign_organisation_user(self.userL1, self.organisationB)
        self.caseX.assign_organisation_user(self.userL2, self.organisationB)

        self.organisationB.assign_case(self.caseY, ROLE_APPLICANT)
        self.organisationC.assign_case(self.caseY, ROLE_DOMESTIC_PRODUCER)
        # user B1 and C1 (admin) has implied access to caseY
        # user L1 (normal) is given acess to caseY/org b
        self.caseY.assign_organisation_user(self.userL1, self.organisationB)

    def test_organisations_have_correct_roles_assigned(self):
        """
        Test organisations have their assigned role in their cases
        (this should be no different from simple case)
        """
        assert self.caseX.has_organisation(self.organisationA, role=ROLE_APPLICANT)
        assert not self.caseX.has_organisation(self.organisationA, role=ROLE_DOMESTIC_PRODUCER)
        assert self.caseX.has_organisation(self.organisationB, role=ROLE_DOMESTIC_PRODUCER)
        assert not self.caseX.has_organisation(self.organisationB, role=ROLE_APPLICANT)
        assert not self.caseX.has_organisation(self.organisationC, role=ROLE_APPLICANT)
        assert not self.caseX.has_organisation(self.organisationC, role=ROLE_DOMESTIC_PRODUCER)

        assert not self.caseY.has_organisation(self.organisationA, role=ROLE_APPLICANT)
        assert not self.caseY.has_organisation(self.organisationA, role=ROLE_DOMESTIC_PRODUCER)
        assert self.caseY.has_organisation(self.organisationB, role=ROLE_APPLICANT)
        assert not self.caseY.has_organisation(self.organisationB, role=ROLE_DOMESTIC_PRODUCER)
        assert not self.caseY.has_organisation(self.organisationC, role=ROLE_APPLICANT)
        assert self.caseY.has_organisation(self.organisationC, role=ROLE_DOMESTIC_PRODUCER)

    def test_users_are_in_correct_organisations(self):
        """
        Test a user can view cases to which they have been assigned
        """
        assert self.userA1.userprofile.all_organisations == [self.organisationA]
        assert self.userA2.userprofile.all_organisations == [self.organisationA]
        assert self.userB1.userprofile.all_organisations == [self.organisationB]
        assert self.userB2.userprofile.all_organisations == [self.organisationB]
        assert set(self.userL1.userprofile.all_organisations) == set(
            [self.organisationA, self.organisationB]
        )
        assert set(self.userL2.userprofile.all_organisations) == set(
            [self.organisationB, self.organisationC]
        )

    def _test_users_can_see_cases(self):
        """
        Test a user can view cases to which they have been assigned
        """

        # we need to specify a user and an organisation because users can have multiple orgs
        assert self.userA1.can_do("VIEW_CASE", self.organisationA, self.caseX)
        assert not self.userA1.can_do("VIEW_CASE", self.organisationB, self.caseX)
        # should the below fail or raise an exception? org C isn't in case X!
        assert not self.userA1.can_do("VIEW_CASE", self.organisationC, self.caseX)
        assert not self.userA2.can_do("VIEW_CASE", self.organisationA, self.caseY)
        assert not self.userA2.can_do("VIEW_CASE", self.organisationB, self.caseY)
        assert not self.userA2.can_do("VIEW_CASE", self.organisationC, self.caseY)

        # and/or...
        assert list(self.userA1.get_cases(self.organisationA)) == [self.caseX]
        assert list(self.userA1.get_cases(self.organisationB)) == []
        assert list(self.userA1.get_cases(self.organisationC)) == []
        assert list(self.userA2.get_cases(self.organisationA)) == [self.caseX]
        assert list(self.userA2.get_cases(self.organisationB)) == []
        assert list(self.userA2.get_cases(self.organisationC)) == []
        assert list(self.userB1.get_cases(self.organisationA)) == []
        assert list(self.userB1.get_cases(self.organisationB)) == [self.caseX, self.caseY]
        assert list(self.userB1.get_cases(self.organisationC)) == []
        assert list(self.userB2.get_cases(self.organisationA)) == []
        assert list(self.userB2.get_cases(self.organisationB)) == [self.caseX]
        assert list(self.userB2.get_cases(self.organisationC)) == []
        assert list(self.userL1.get_cases(self.organisationA)) == [self.caseX]
        assert list(self.userL1.get_cases(self.organisationB)) == [self.caseX, self.caseY]
        assert list(self.userL1.get_cases(self.organisationC)) == []
        assert list(self.userL2.get_cases(self.organisationA)) == []
        assert list(self.userL2.get_cases(self.organisationB)) == [self.caseX]
        assert list(self.userL2.get_cases(self.organisationC)) == [self.caseY]

    def _test_users_can_upload_docs_to_their_own_cases(self):
        """
        Test that a user can upload documents to a given case on behalf of a given org
        """
        assert self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userA1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userA2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert not self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userB1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        # org B is in case Y, but user B2 isn't enabled for case Y
        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userB2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert self.userL1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert self.userL1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userL1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userL1.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert self.userL1.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert not self.userL1.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

        assert not self.userL2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseX)
        assert self.userL2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseX)
        assert not self.userL2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseX)
        assert not self.userL2.can_do("UPLOAD_DOCUMENT", self.organisationA, self.caseY)
        assert not self.userL2.can_do("UPLOAD_DOCUMENT", self.organisationB, self.caseY)
        assert self.userL2.can_do("UPLOAD_DOCUMENT", self.organisationC, self.caseY)

    """
    other tests that we need:
    Inviting users:
        A1 (as admin) can:
            - invite new users to org A
            - make A2 an admin of org A
            - revoke admin from A2 (if A2 is already an admin)
        A2 (not admin) can't invite users, make admin, or revoke admin
    Multi-case organisations:
        Org A is applicant for both case X and case Y
        Different users have different access cases
        Lawyers might be involved here too...
    """
