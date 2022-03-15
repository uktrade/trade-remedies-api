"""
The ModelSecurity framework determines access to individual users for a combination
of a model (e.g. case or organisation) and a specific action and/or role.

Access is defined by sets of fine grained actions, grouped into Roles, which are
assigned to user and model. A set of access rules can be:
    User X has Applicant access on Case 123
    User X has Respondent access on case 456

A mixin is provided to be mixed in to the user model providing handy
shortcuts to determine this access for any given model or to assign it.
"""

from django.db import models
from functools import singledispatch
from django.contrib.auth.models import Group
from django.conf import settings
from django.utils import timezone
from core.base import SimpleBaseModel
from organisations.constants import CONTRIBUTOR_ORG_CASE_ROLE
from security.constants import ROLE_PREPARING


@singledispatch
def get_role(role):
    """
    A single dispatch to return a role from either a role instance or
    the role name string.
    """
    return role


@get_role.register(str)
def _(role):  # noqa
    return CaseRole.objects.get(key=role)


@get_role.register(int)
def _(role):  # noqa
    return CaseRole.objects.get(id=role)


@singledispatch
def get_action(action):
    """
    A single dispatch to return an action from either an action instance or
    the action id string.
    """
    return action


@get_action.register(str)
def _(action):  # noqa
    return CaseAction.objects.get(id=action)


@singledispatch
def get_security_group(group):
    """
    A single dispatch to return a security group from either a group instance or
    the group name string.
    """
    return group


@get_security_group.register(str)
def _(group):  # noqa
    return Group.objects.get(name=group)


class CaseAction(models.Model):
    """
    A granular action that can be performed in the system
    """

    id = models.CharField(primary_key=True, max_length=50, null=False, blank=False)
    name = models.CharField(max_length=50, null=False, blank=False)

    def __str__(self):
        return self.name


class CaseRole(models.Model):
    """
    A user's role within a case, which encapulate a set of
    allowed actions, on the specific case.
    Roles can be identified by id or unique key
    """

    name = models.CharField(max_length=100, null=False, blank=False)
    key = models.CharField(max_length=100, null=True, blank=True, unique=True)
    order = models.SmallIntegerField(default=0)
    plural = models.CharField(max_length=100, null=True, blank=True)
    actions = models.ManyToManyField(CaseAction)
    allow_cw_create = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "plural": self.plural,
            "order": self.order,
            "key": self.key,
            "allow_cw_create": self.allow_cw_create,
        }

    def contributor_or_interested(self):
        if self.key in CONTRIBUTOR_ORG_CASE_ROLE:
            return "Contributor"
        return "Interested party"


class OrganisationCaseRoleManager(models.Manager):
    def case_role(self, organisation, case):
        return self.filter(organisation=organisation, case=case).first()

    def case_prepared(self, organisation_id):
        return self.exclude(role=CaseRole.objects.get(id=ROLE_PREPARING)).filter(
            organisation__id=organisation_id
        )

    def has_organisation_case_role(self, organisation, case, role=None):
        """
        Return True if the organisation has role in case
        :param organisation: Organisation instance
        :param case: Case instance
        :param role: Optional CaseRole instance or name
        """
        org_role = self.filter(organisation=organisation, case=case)
        if role:
            org_role = org_role.filter(role=get_role(role))
        return org_role.exists()

    def can_do_action(self, user, organisation, case, action):
        """
        Determine if a user of an organistion can perform a given action on a case.
        This is True if
            The organisation is a participant in the case.
            The role of the organisation in the case allows for the action
            The user is a member of the organisation
            The user has access to the case as part of this organisation
            (i.e. they have been granted access or are admin)
        """
        org_role = self.filter(
            organisation=organisation,
            organisation__organisationuser__user=user,
            case=case,
            role__actions=get_action(action),
        )
        if org_role and user.has_case_access(case, organisation):
            return True
        return False

    def assign_organisation_case_role(
        self,
        organisation,
        case,
        role,
        sampled=False,
        created_by=None,
        approved_by=None,
        approved_at=None,
    ):
        """
        Attempt to assign a user to a given model and role.
        Returns a tuple with the model created/fetched and a boolean to designate
        if the role was newly assigned or alrady existed.
        If the case role is set but different to what is provided it will be updated.
        """
        role = get_role(role)
        created = False
        try:
            case_role = self.get(organisation=organisation, case=case)
            if role != case_role.role:
                case_role.role = role
        except OrganisationCaseRole.DoesNotExist:
            if approved_by and not approved_at:
                approved_at = timezone.now()
            case_role = OrganisationCaseRole(
                organisation=organisation,
                case=case,
                role=role,
                sampled=sampled,
                created_by=created_by,
                approved_by=approved_by,
                approved_at=approved_at,
            )
            created = True
        case_role.set_user_context(created_by)
        case_role.save()
        return case_role, created

    def revoke_organisation_case_role(self, organisation, case, role=None):
        """
        Delete model security records for a given user and model,
        and optionally a specific role.
        TODO: Audit log
        """
        org_case_role = self.filter(organisation=organisation, case=case)
        if role:
            org_case_role = org_case_role.filter(role=get_role(role))
        return org_case_role.delete()

    def get_organisation_role(self, case, organisation, outer=None):
        """
        Return the case role of a given organisation
        """
        try:
            org_case_role = self.select_related("role", "case").get(
                case=case, organisation=organisation
            )
            return org_case_role if outer else org_case_role.role
        except OrganisationCaseRole.DoesNotExist:
            return None


class OrganisationCaseRole(SimpleBaseModel):
    """
    Connect a model (case, organisation etc.) to a user and a role.
    """

    organisation = models.ForeignKey(
        "organisations.Organisation", null=False, blank=False, on_delete=models.CASCADE
    )
    case = models.ForeignKey("cases.Case", null=False, blank=False, on_delete=models.CASCADE)
    role = models.ForeignKey("CaseRole", null=False, blank=False, on_delete=models.CASCADE)
    sampled = models.BooleanField(default=False)
    non_responsive = models.BooleanField(default=False)
    validated_at = models.DateTimeField(null=True, blank=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="validated_by"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="approved_by"
    )
    auth_contact = models.ForeignKey(
        "contacts.Contact",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="loa_contact",
    )

    objects = OrganisationCaseRoleManager()

    class Meta:
        unique_together = ["organisation", "case"]

    def __str__(self):
        return f"{self.organisation.name} {self.role.name} {self.case.name}"

    def to_dict(self, case=None, fields=None):
        _dict = self.to_embedded_dict()
        _dict.update(self.organisation.to_dict(case=case, fields=fields))
        return _dict

    def to_embedded_dict(self, fields=None):
        _dict = self.organisation.to_embedded_dict()
        _dict.update(
            {
                "sampled": self.sampled,
                "non_responsive": self.non_responsive,
                "role": self.role.to_dict(),
                "validated_at": self.validated_at.strftime(settings.API_DATETIME_FORMAT)
                if self.validated_at
                else None,
                "validated_by": self.validated_by.to_embedded_dict() if self.validated_by else None,
                "approved_at": self.approved_at.strftime(settings.API_DATETIME_FORMAT)
                if self.approved_at
                else None,
                "approved_by": self.approved_by.to_embedded_dict() if self.approved_by else None,
            }
        )
        if self.auth_contact:
            _dict["auth_contact"] = self.auth_contact.to_dict()
        return _dict


class OrganisationUserManager(models.Manager):
    def assign_user(self, user, organisation, security_group, confirmed=True):
        """
        Assign a user to an organisation with a security group.
        :param user: A user instance
        :param organisation: An organisation instance
        :param security_group: A security Group instance or name
        """
        org_user, created = OrganisationUser.objects.get_or_create(
            organisation=organisation, user=user
        )
        _group = get_security_group(security_group)
        if created or org_user.security_group != _group:
            org_user.security_group = _group
            org_user.save()
        if confirmed != org_user.confirmed:
            org_user.confirmed = confirmed
            org_user.save()
        return org_user

    def user_organisation_security_group(self, user, organisation):
        org_user = self.filter(organisation=organisation, user=user).first()
        if org_user:
            return org_user.security_group
        return None


class OrganisationUser(SimpleBaseModel):
    """
    A membership of a user in an organisation and the security group associated with it.
    Note that a user might be a member of multiple organisations,
    but assigned only once to each organisation,
    although this is not currently in use and a user is considered
    a direct employee of one organisation.
    """

    organisation = models.ForeignKey(
        "organisations.Organisation", null=False, blank=False, on_delete=models.CASCADE
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, blank=False, on_delete=models.CASCADE)
    security_group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.CASCADE)
    confirmed = models.BooleanField(default=True)

    objects = OrganisationUserManager()

    class Meta:
        unique_together = ["organisation", "user"]

    def __str__(self):
        return f"{self.user.name} member of {self.organisation} as {self.security_group.name}"

    def enhance_dict(self):
        return {
            "user_id": str(self.user_id),
            "confirmed": self.confirmed,
            "security_group": self.security_group.name,
        }

    def to_embedded_dict(self):
        _dict = self.organisation.to_embedded_dict()
        _dict.update(self.enhance_dict())
        return _dict

    def to_dict(self):
        _dict = self.organisation.to_dict()
        _dict.update(self.enhance_dict())
        return _dict

    def to_user_dict(self):
        _dict = {"organisation_id": self.organisation.id}
        _dict.update(self.enhance_dict())
        _dict.update(self.user.to_dict())
        return _dict


class UserCase(SimpleBaseModel):
    """
    Case access per user set explicitly. Organisation Administrator users will have implicit access
    to all cases but explicit access can still be set. This model allows for a future extension of
    the type of access a user might have in the case.
    A user's participation in a case might require approval by the TRA. The confirmed key, which
    defaults to True, determiens the confirmation state of the user in the case. confirmed_by/at
    determine who and when confirmation took place IF it was required. Users invited by the TRA
    or users creating the case do not require confirmation. However, invited 3rd parties with
    letter of authrotiry do.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=False, blank=False, on_delete=models.CASCADE)
    case = models.ForeignKey("cases.Case", null=False, blank=False, on_delete=models.CASCADE)
    organisation = models.ForeignKey(
        "organisations.Organisation", null=True, blank=True, on_delete=models.CASCADE
    )
    confirmed = models.BooleanField(default=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="confirmed_by"
    )

    class Meta:
        unique_together = ["user", "case", "organisation"]

    def __str__(self):
        return f"{self.user.name} can access {self.case.name}"

    def to_dict(self):
        _dict = self.to_embedded_dict()
        _dict["user"]["organisation"] = _dict["organisation"]
        _dict["organisation"] = self.organisation.to_embedded_dict() if self.organisation else {}
        _dict["confirmed"] = self.confirmed
        if self.confirmed:
            if self.confirmed_at:
                _dict["confirmed_at"] = self.confirmed_at.strftime(settings.API_DATETIME_FORMAT)
            if self.confirmed_by:
                _dict["confirmed_by"] = {
                    "id": str(self.confirmed_by.id),
                    "name": self.confirmed_by.name,
                }
        return _dict

    def to_embedded_dict(self):
        _dict = {
            "case": self.case.to_minimal_dict(attrs={"initiated_at"}),
            "user": self.user.to_embedded_dict(groups=True),
            "organisation": {
                "id": str(self.user.organisation.organisation.id)
                if self.user.organisation
                else None,
                "name": self.user.organisation.organisation.name
                if self.user.organisation
                else None,
            },
            "created_at": self.created_at.strftime(settings.API_DATETIME_FORMAT),
        }

        if self.organisation:
            _dict.update(
                {
                    "representing": {
                        "id": str(self.organisation.id),
                        "name": self.organisation.name,
                        "companies_house_id": self.organisation.companies_house_id,
                        "address": {
                            "address": self.organisation.address,
                            "post_code": self.organisation.post_code,
                            "country": self.organisation.country.name,
                        },
                    }
                }
            )
        return _dict


class CaseSecurityMixin:
    def user_case_role(self, organisation, case):
        """
        Return the role of a user, via their organisation, to a case
        """
        org_case_role = OrganisationCaseRole.objects.case_role(organisation, case)
        return org_case_role

    def can_do(self, action, organisation, case):
        return OrganisationCaseRole.objects.can_do_action(
            user=self, organisation=organisation, case=case, action=action
        )

    def organisation_security_group(self, organisation):
        """
        Return this user's security group in an organisation
        """
        return OrganisationUser.objects.user_organisation_security_group(self, organisation)

    def has_case_access(self, case, organisation):
        """
        Returns True if the user has access to a given case for an organisation.
        That is True if the user is either an admin of the the organisation which is a participant
        in the case, or the user has explicit access to it.
        """
        can_access = self.organisation_security_group(organisation) == get_security_group(
            "Organisation Owner"
        )
        participant_organisation = OrganisationCaseRole.objects.has_organisation_case_role(
            organisation=organisation, case=case
        )
        if not can_access:
            can_access = UserCase.objects.filter(case=case, user=self).exists()
        return can_access and participant_organisation

    def has_group(self, group):
        """
        Return True if the user is directly assigned the given security group.
        TRA users can be assigned security groups which allows them broader access
        :param group: The Group instance or name
        """
        return get_security_group(group) in self.get_groups()
