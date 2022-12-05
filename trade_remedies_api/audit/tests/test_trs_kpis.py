from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import mock_open, patch

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from model_bakery import baker

from cases.constants import (
    SUBMISSION_STATUS_REGISTER_INTEREST_RECEIVED,
    SUBMISSION_TYPE_APPLICATION,
    SUBMISSION_TYPE_REGISTER_INTEREST,
)
from cases.models import Case, Submission, SubmissionStatus

time_periods = [datetime.today().replace(day=1, month=i) for i in range(1, 7)]


@pytest.fixture
def load_sample_data():
    # create public group
    group = baker.make(Group, name="Organisation Owner")

    for tp in time_periods:
        public_user = baker.make(
            "core.UserProfile", email_verified_at=tp, user__created_at=tp, make_m2m=True
        )
        group.user_set.add(public_user.user)
        baker.make("cases.Case", submitted_at=tp, created_at=tp, make_m2m=True)

        # initated in 2 weeks
        wk_2 = tp + timedelta(days=14)
        baker.make("cases.Case", initiated_at=wk_2, submitted_at=tp, created_at=tp, make_m2m=True)

        submission = baker.make("cases.Submission", created_at=tp, make_m2m=True)

        baker.make(
            "cases.SubmissionDocument",
            created_by=public_user.user,
            submission=submission,
            downloads=10,
        )
    case_object = Case.objects.first()
    for i in range(4):
        Submission.objects.create(
            type_id=SUBMISSION_TYPE_REGISTER_INTEREST,
            status_id=SUBMISSION_STATUS_REGISTER_INTEREST_RECEIVED,
            case=case_object
        )
    for i in range(5):
        Submission.objects.create(
            type_id=SUBMISSION_TYPE_REGISTER_INTEREST,
            status=SubmissionStatus.objects.get(
                type_id=SUBMISSION_TYPE_REGISTER_INTEREST, sufficient=True
            ),
            case=case_object
        )
    Submission.objects.create(
        type_id=SUBMISSION_TYPE_APPLICATION,
        case=case_object,
        status=SubmissionStatus.objects.get(
            type_id=SUBMISSION_TYPE_APPLICATION, received=True
        )
    )


@pytest.mark.django_db
def test_get_all_kpis(load_sample_data):
    out = StringIO()
    call_command("trs_kpis", stdout=out)

    assert "Verified Public user count: 6" in out.getvalue()
    assert "Case registrations submitted: 4" in out.getvalue()
    assert "Case registrations accepted: 5" in out.getvalue()
    assert "Total case applications submitted: 1" in out.getvalue()
    assert "Submissions count: 16" in out.getvalue()
    assert "Files uploaded by public users count: 6" in out.getvalue()
    assert "Total files downloaded: 60" in out.getvalue()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "date_from,date_to, user_count",
    [
        (time_periods[0].strftime("%Y-%m-%d"), time_periods[i].strftime("%Y-%m-%d"), i)
        for i in range(1, len(time_periods), 2)
    ],
)
def test_get_kpis_period(date_from, date_to, user_count, load_sample_data):
    out = StringIO()
    call_command("trs_kpis", date_from=date_from, date_to=date_to, stdout=out)

    assert f"Verified Public user count: {user_count}" in out.getvalue()
    assert "Total files downloaded: 60" in out.getvalue()


@pytest.mark.django_db
def test_creating_outfile_no_trailing_backslash(load_sample_data):
    out = StringIO()
    outpath = "/tmp/outpath"
    m = mock_open()
    with patch("audit.management.commands.trs_kpis.open", m, create=True):
        call_command("trs_kpis", outpath=outpath, stdout=out)

    m.assert_called_with(f"{outpath}/outfile.txt", "a")


@pytest.mark.django_db
def test_creating_outfile_trailing_backslash(load_sample_data):
    out = StringIO()
    outpath = "/tmp/outpath/"
    m = mock_open()
    with patch("audit.management.commands.trs_kpis.open", m, create=True):
        call_command("trs_kpis", outpath=outpath, stdout=out)

    m.assert_called_with(f"{outpath}outfile.txt", "a")
