import datetime
import json
import pytest

from django.utils import timezone

pytestmark = [pytest.mark.version2, pytest.mark.functional]


def test_email_verify():
    pass  # Test right response for valid email verify code


def test_email_verify_fail():
    pass  # Test right response for invalid email verify code
