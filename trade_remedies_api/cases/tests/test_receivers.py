import logging
import pytest


import cases.receivers as receivers
from cases.models import Case
from core.models import User, UserCase


@pytest.fixture
def user_sender(mocker):
    """Fake receiver sender for a user."""
    sender = mocker.Mock(spec=User)
    return sender


@pytest.fixture
def case_sender(mocker):
    """Fake receiver sender for a case."""
    sender = mocker.Mock(spec=Case)
    return sender


@pytest.fixture
def org_sender(mocker):
    """Fake receiver sender for an organisation."""
    sender = mocker.Mock(spec=Case)
    return sender


@pytest.fixture
def user_case_sender(mocker):
    """Fake receiver sender for a user case."""
    sender = mocker.Mock(spec=UserCase)
    return sender


@pytest.fixture
def user(mocker):
    """Fake User instance."""
    user = mocker.Mock()
    user.id = "001"
    user.email = "foo@bar.com"  # /PS-IGNORE
    return user


@pytest.fixture
def case(mocker):
    """Fake Case instance."""
    case = mocker.Mock()
    case.id = "002"
    case.name = "case-002"
    return case


@pytest.fixture
def org(mocker):
    """Fake Organisation instance."""
    org = mocker.Mock()
    org.id = "003"
    org.name = "org-003"
    return org


@pytest.fixture
def user_case(mocker, user, case, org):
    """Fake UserCase instance."""
    instance = mocker.Mock()
    instance.user = user
    instance.case = case
    instance.organisation = org
    return instance


def test_log_deleted_usercase(caplog, user_case_sender, user_case):
    receivers.log_deleted_usercase(user_case_sender, user_case)
    expected = (
        "UserCase record deleted: user_id = 001, email = foo@bar.com, "  # /PS-IGNORE
        "case_id = 002, case = case-002, organisation_id = 003, "
        "organisation = org-003"
    )
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_user(caplog, user_sender, user):
    receivers.log_deleted_user(user_sender, user)
    expected = "User record deleted: user_id = 001, email = foo@bar.com"  # /PS-IGNORE
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_case(caplog, case_sender, case):
    receivers.log_deleted_case(case_sender, case)
    expected = "Case record deleted: case_id = 002, case = case-002"
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_organisation(caplog, org_sender, org):
    receivers.log_deleted_organisation(org_sender, org)
    expected = "Organisation record deleted: organisation_id = 003, " "organisation = org-003"
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_usercase_missing_user_id(mocker, caplog, user_case_sender, user_case):
    bad_user = mocker.Mock(spec=["email"])
    bad_user.email = "foo@bar.com"  # /PS-IGNORE
    user_case.user = bad_user
    receivers.log_deleted_usercase(user_case_sender, user_case)
    expected = (
        "UserCase record deleted: user_id = unknown, email = foo@bar.com, "  # /PS-IGNORE
        "case_id = 002, case = case-002, organisation_id = 003, "
        "organisation = org-003"
    )
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_usercase_missing_case_id(mocker, caplog, user_case_sender, user_case):
    bad_case = mocker.Mock(spec=["name"])
    bad_case.name = "case-005"
    user_case.case = bad_case
    receivers.log_deleted_usercase(user_case_sender, user_case)
    expected = (
        "UserCase record deleted: user_id = 001, email = foo@bar.com, "  # /PS-IGNORE
        "case_id = unknown, case = case-005, organisation_id = 003, "
        "organisation = org-003"
    )
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_user_missing_id(mocker, caplog, user_sender):
    bad_user = mocker.Mock(spec=["email"])
    bad_user.email = "foo@bar.com"  # /PS-IGNORE
    receivers.log_deleted_user(user_sender, bad_user)
    expected = "User record deleted: user_id = unknown, email = foo@bar.com"  # /PS-IGNORE
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_usercase_missing_inst(mocker, caplog, user_case_sender, user_case):
    bad_user = mocker.Mock(spec=["email"])
    bad_user.email = "foo@bar.com"  # /PS-IGNORE
    user_case.user = bad_user
    receivers.log_deleted_usercase(user_case_sender, None)
    expected = "Unable to log all details because: 'NoneType' object has no attribute 'user'"
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_user_missing_inst(caplog, user_sender):
    receivers.log_deleted_user(user_sender, None)
    expected = "User record deleted: user_id = unknown, email = unknown"
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_case_missing_inst(caplog, case_sender):
    receivers.log_deleted_case(case_sender, None)
    expected = "Case record deleted: case_id = unknown, case = unknown"
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text


def test_log_deleted_org_missing_inst(caplog, org_sender):
    receivers.log_deleted_organisation(org_sender, None)
    expected = "Organisation record deleted: organisation_id = unknown, organisation = unknown"
    with caplog.at_level(logging.INFO):
        assert expected in caplog.text
