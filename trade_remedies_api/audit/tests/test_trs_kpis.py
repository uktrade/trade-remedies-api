import pytest

import itertools

from io import StringIO

from datetime import datetime

from model_bakery import baker

from django.core.management import call_command

from security.constants import SECURITY_GROUPS_PUBLIC

time_periods = [datetime.today().replace(day=1, month=i) for i in range(1, 7)]


@pytest.fixture
def load_sample_data():
    public_users = baker.make('core.UserProfile', email_verify_code=time_periods[0], created_by__groups__name__in=SECURITY_GROUPS_PUBLIC, _quantity=3, make_m2m=True)
    cases = baker.make('cases.Case', _quantity=3)
    submissions = baker.make("cases.Submission", _quantity=3)
    submission_documents = baker.make("cases.SubmissionDocument", submission=submissions[0], downloads=10, _quantity=3)


@pytest.mark.django_db
def test_get_all_kpis(load_sample_data):
    out = StringIO()
    call_command("trs_kpis", stdout=out)

    assert "Total files downloaded: 30" in out.getvalue()


@pytest.mark.django_db
@pytest.mark.parametrize("date_from,date_to", [(time_periods[0].strftime("%Y-%m-%d"), time_periods[i].strftime("%Y-%m-%d")) for i in range(1, len(time_periods), 2)])
def test_get_kpis_period(date_from, date_to, load_sample_data):
    out = StringIO()
    call_command("trs_kpis", date_from=date_from, date_to=date_to, stdout=out)

    assert "Total files downloaded: 30" in out.getvalue()
