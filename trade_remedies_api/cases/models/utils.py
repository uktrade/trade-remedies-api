import uuid
from functools import singledispatch
from .case import Case
from .submissiontype import SubmissionType
from .submissionstatus import SubmissionStatus


@singledispatch
def get_case(case) -> Case:
    """
    A single dispatch to return a case from either a case instance or
    the case id.
    """
    return case


@get_case.register(str)
def _(case) -> Case:  # noqa
    return Case.objects.get_case(id=case)


@get_case.register(uuid.UUID)
def _(case) -> Case:  # noqa
    return Case.objects.get_case(id=case)


@singledispatch
def get_submission_type(submission_type):
    """
    A single dispatch to return a Submission Type from either an instance or
    the name
    """
    return submission_type


@get_submission_type.register(int)
def _(submission_type):  # noqa
    return SubmissionType.objects.get(id=submission_type)


@get_submission_type.register(str)
def _(submission_type):  # noqa
    if submission_type.isdigit():
        return get_submission_type(int(submission_type))
    else:
        return SubmissionType.objects.get(name=submission_type)


@singledispatch
def get_submission_status(submission_status):
    """
    A single dispatch to return a Submission Type from either an instance or
    the name
    """
    return submission_status


@get_submission_status.register(int)
def _(submission_status):  # noqa
    return SubmissionStatus.objects.select_related("type").get(id=submission_status)
