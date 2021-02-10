import pytest
from django.core.management import call_command


@pytest.fixture
def audits(mocker):
    """Fake audit logs.

    Creates a list of fake audit models provides a mock `case_title` property
    that can be checked for access using `test.assert_called_once_with()` on
    the audit item.

    Uses https://docs.python.org/dev/library/unittest.mock.html#unittest.mock.PropertyMock
    """
    audits = []
    for i in range(3):
        fake_audit = mocker.MagicMock()
        fake_audit.test = mocker.PropertyMock(return_value=f"title {i}")
        type(fake_audit).case_title = fake_audit.test
        audits.append(fake_audit)
    return audits


@pytest.fixture
def fake_audit_model(mocker, audits):
    """Fake audit model.

    Creates a fake audit model and populates with items form `audits` fixture.
    """
    fake_model = mocker.MagicMock()
    queryset = mocker.MagicMock()
    queryset.count.return_value = len(audits)
    queryset.iterator.return_value = iter(audits)
    fake_model.objects.all = mocker.MagicMock(return_value=queryset)
    return fake_model


def test_patch(mocker, fake_audit_model):
    # Patch patch_audit management command module namespace's `Audit`
    # with our fake audit model
    mocker.patch('audit.management.commands.patch_audit.Audit', fake_audit_model)
    call_command("patch_audit")
    for audit in fake_audit_model.all():
        audit.test.assert_called_once_with()
