"""
Implement behave test steps for user security tests.
"""
from behave import given, when, then
from core.models import User
from organisations.models import Organisation
from cases.models import Case
from security.constants import ROLE_APPLICANT

PASSWORD = "A7Hhfa!jfaw@f"


# should work out a way of merging this one and the one below
@given('I am a public user "{email}"')  # noqa: F811
def step_impl(context, email):
    context.user = User.objects.create(email=email, password=PASSWORD)
    return context


@given('there is a public user "{email}"')  # noqa: F811
def step_impl(context, email):
    if "public_users" not in context:
        context.public_users = []
    context.public_users.append(User.objects.create(email=email, password=PASSWORD))
    return context


@given('I am owner of the organisation "{orgname}"')  # noqa: F811
def step_impl(context, orgname):
    context.organisation = Organisation.objects.create(name=orgname)
    context.organisation.assign_user(context.user, context.org_group_owner)
    return context


@given('I am not owner of the organisation "{orgname}"')  # noqa: F811
def step_impl(context, orgname):
    context.organisation = Organisation.objects.create(name=orgname)
    context.organisation.assign_user(context.user, context.org_group_user)
    return context


@given('I have access to case "{casename}"')  # noqa: F811
def step_impl(context, casename):
    context.case = Case.objects.create(name=casename)
    # should we separate this out?
    context.organisation.assign_case(context.case, ROLE_APPLICANT)
    context.case.assign_organisation_user(context.user, context.organisation)
    return context


@when('I invite "{email}" to "{orgname}"')  # noqa: F811
def step_impl(context, email, orgname):
    test_user = User.objects.get(email=email)
    test_org = Organisation.objects.get(name=orgname)
    context.organisation.assign_user(test_user, context.org_group_user)
    return context


@then('"{email}" is a user of "{orgname}"')  # noqa: F811
def step_impl(context, email, orgname):
    test_user = User.objects.get(email=email)
    test_org = Organisation.objects.get(name=orgname)
    assert test_user.organisations == [test_org]
    return context


@then('"{email}" is not a user of "{orgname}"')  # noqa: F811
def step_impl(context, email, orgname):
    test_user = User.objects.get(email=email)
    test_org = Organisation.objects.get(name=orgname)
    assert not test_user.organisations == [test_org]
    return context


@then('I am owner of the organisation "{orgname}"')  # noqa: F811
def step_impl(context, orgname):
    test_org = Organisation.objects.get(name=orgname)
    assert test_org.has_user_role(context.user, context.org_group_owner)
    return context


@then('I am not owner of the organisation "{orgname}"')  # noqa: F811
def step_impl(context, orgname):
    test_org = Organisation.objects.get(name=orgname)
    assert not test_org.has_user_role(context.user, context.org_group_owner)
    return context


@then('"{email}" is not owner of "{orgname}"')  # noqa: F811
def step_impl(context, email, orgname):
    test_user = User.objects.get(email=email)
    test_org = Organisation.objects.get(name=orgname)
    assert not test_org.has_user_role(test_user, context.org_group_owner)
    return context


@when('I make "sue@test.com" an owner of "Org A"')  # noqa: F811 #PS-IGNORE
def step_impl(context, email):
    test_user = User.objects.get(email=email)
    raise NotImplementedError('STEP: When I make "sue@test.com" an owner of "Org A"')#PS-IGNORE


"""
"""


@when("I invite a new member to my Organisation account")  # noqa: F811
def step_impl(context):
    raise NotImplementedError("STEP: When I invite a new member to my Organisation account")


@then("they become a  TRA service user for my organisation")  # noqa: F811
def step_impl(context):
    raise NotImplementedError("STEP: Then they become a  TRA service user for my organisation")


@then("I can give them permssion to access a case")  # noqa: F811
def step_impl(context):
    raise NotImplementedError("STEP: Then I can give them permssion to access a case")


@then("they are not an Owner")  # noqa: F811
def step_impl(context):
    raise NotImplementedError("STEP: Then they are not an Owner")
