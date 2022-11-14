import pytest

from io import StringIO

from datetime import datetime, timedelta

from model_bakery import baker

from django.core.management import call_command
from django.contrib.auth.models import Group

time_periods = [datetime.today().replace(day=1, month=i) for i in range(1, 7)]


@pytest.fixture
def load_sample_data():

    # create public group
    group = baker.make(Group, name="Organisation Owner")

    for tp in time_periods:
        public_user = baker.make('core.UserProfile', email_verified_at=tp, user__created_at=tp, make_m2m=True)
        group.user_set.add(public_user.user)
        baker.make('cases.Case', submitted_at=tp, created_at=tp, make_m2m=True)

        # initated in 2 weeks
        wk_2 = tp + timedelta(days=14)
        baker.make('cases.Case', initiated_at=wk_2, submitted_at=tp, created_at=tp, make_m2m=True)

        submission = baker.make("cases.Submission", created_at=tp, make_m2m=True)

        baker.make("cases.SubmissionDocument", created_by=public_user.user, submission=submission, downloads=10)


@pytest.mark.django_db
def test_get_all_kpis(load_sample_data):
    out = StringIO()
    call_command("trs_kpis", stdout=out)

    assert "Verified Public user count: 6" in out.getvalue()
    assert "Case Registration request count: 12" in out.getvalue()
    assert "Case applications accepted count: 6" in out.getvalue()
    assert "Submissions count: 6" in out.getvalue()
    assert "Files uploaded by public users count: 6" in out.getvalue()
    assert "Total files downloaded: 60" in out.getvalue()


@pytest.mark.django_db
@pytest.mark.parametrize("date_from,date_to, user_count", [(time_periods[0].strftime("%Y-%m-%d"), time_periods[i].strftime("%Y-%m-%d"), i) for i in range(1, len(time_periods), 2)])
def test_get_kpis_period(date_from, date_to, user_count, load_sample_data):
    out = StringIO()
    call_command("trs_kpis", date_from=date_from, date_to=date_to, stdout=out)

    assert f"Verified Public user count: {user_count}" in out.getvalue()
    assert "Total files downloaded: 60" in out.getvalue()
