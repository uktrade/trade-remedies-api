import os
import logging
import datetime
import pytz
import uuid
import json
from random import randint
from functools import singledispatch
from django.db import models, transaction
from django.utils import timezone, crypto
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import PermissionsMixin, Group, Permission
from django.contrib.auth.base_user import BaseUserManager, AbstractBaseUser
from django.contrib.auth.password_validation import validate_password
from django.contrib.postgres import fields
from rest_framework.authtoken.models import Token
from audit.models import Audit
from security.constants import (
    SECURITY_GROUP_TRA_HEAD_OF_INVESTIGATION,
    SECURITY_GROUPS_TRA,
    SECURITY_GROUPS_TRA_ADMINS,
    SECURITY_GROUPS_PUBLIC,
    SECURITY_GROUP_ORGANISATION_OWNER,
    SECURITY_GROUP_ORGANISATION_USER,
    DEFAULT_ADMIN_PERMISSIONS,
    DEFAULT_USER_PERMISSIONS,
    SOS_SECURITY_GROUPS,
)
from security.models import CaseSecurityMixin, UserCase, OrganisationUser
from core.notifier import send_sms
from timezone_field import TimeZoneField
from phonenumbers.phonenumberutil import NumberParseException
from .exceptions import UserExists
from .tasks import send_mail
from .decorators import method_cache
from .constants import SAFE_COLOURS, DEFAULT_USER_COLOUR, TRUTHFUL_INPUT_VALUES
from .utils import convert_to_e164, filter_dict


logger = logging.getLogger(__name__)


@singledispatch
def get_groups(groups):
    return groups


@get_groups.register(list)  # noqa
def _(groups):
    return Group.objects.filter(name__in=groups)


class JobTitle(models.Model):
    name = models.CharField(max_length=250, blank=False, null=False)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_base_user_model(self, email, **kwargs):
        """
        Generate a base user record.
        Does not save the model returned.
        """
        if not email:
            raise ValueError("Users must have an email address")
        normalised_email = email.lower().strip()
        exists = self.filter(email__iexact=normalised_email).first()
        if exists:
            raise UserExists("Email already registered")
        user = self.model(email=normalised_email)
        user.name = kwargs["name"] if kwargs.get("name") else ""

        user.is_active = kwargs.get("is_active", True)
        return user

    def evaluate_sos_membership(self, user, groups):
        if groups:
            from organisations.models import Organisation

            sos_org = Organisation.objects.get(id=settings.SECRETARY_OF_STATE_ORGANISATION_ID)
            if any([grp in SOS_SECURITY_GROUPS for grp in groups]):
                user.assign_to_organisation(sos_org, SECURITY_GROUP_TRA_HEAD_OF_INVESTIGATION)
            else:
                user.remove_from_organisation(sos_org)

    @transaction.atomic
    def create_user(
        self, email, password=None, assign_default_groups=True, groups=None, admin=False, **kwargs
    ):
        """
        Creates and saves a User with the given email and password.
        Along with the user, a profile and contact is also created.
        If an organisation name is provided, it is created and associated with the
        user. Optionally a ready made organisation record can be passed along as well.
        """
        from contacts.models import Contact
        from organisations.models import Organisation

        user = self.create_base_user_model(email, **kwargs)
        # Will raise validationerror if fails validation
        validate_password(password)
        user.set_password(password)
        user.save()
        if assign_default_groups and not groups:
            permissions = DEFAULT_ADMIN_PERMISSIONS if admin is True else DEFAULT_USER_PERMISSIONS
            groups = Group.objects.filter(name__in=permissions)
        if groups:
            for group in get_groups(groups):
                user.groups.add(group)
        self.evaluate_sos_membership(user, groups)
        # Organisation
        organisation_name = kwargs.get("organisation_name")
        organisation = kwargs.get("organisation")
        organisation_address = kwargs.get("organisation_address")
        post_code = kwargs.get("organisation_postcode")
        # Contact and profile details
        phone = kwargs.get("phone")
        country = kwargs.get("country", "GB")
        user_timezone = kwargs.get("timezone")
        if phone:
            try:
                phone = convert_to_e164(phone, country=country)
            except NumberParseException:
                pass

        contact = kwargs.get("contact")
        if not contact:
            contact = Contact.objects.create(
                name=user.name,
                email=user.email,
                organisation=organisation,
                phone=phone,
                address=kwargs.get("contact_address") or organisation_address,
                post_code=kwargs.get("contact_postcode") or post_code,
                country=country,
                created_by=user,
            )
        else:
            contact.phone = phone
            contact.address = kwargs.get("contact_address") or contact.address
            contact.post_code = kwargs.get("contact_postcode") or contact.post_code
            country = country
            contact.save()

        UserProfile.objects.create(
            user=user,
            contact=contact,
            timezone=pytz.timezone(user_timezone) if user_timezone else None,
            colour=str(user.get_user_colour() or "black"),
            job_title_id=kwargs.get("job_title_id"),
        )

        if organisation_name:
            organisation = Organisation.objects.create_or_update_organisation(
                organisation_id=kwargs.get("organisation_id"),
                user=user,
                name=organisation_name,
                address=organisation_address,
                country=kwargs.get("organisation_country"),
                post_code=post_code,
                assign_user=True,
                **filter_dict(
                    kwargs,
                    [
                        "vat_number",
                        "eori_number",
                        "duns_number",
                        "organisation_website",
                        "companies_house_id",
                    ],
                ),
            )
        user.save()
        user.auth_token = Token.objects.create(user=user)
        user.refresh_from_db()
        return user

    @transaction.atomic
    def create_pending_user(
        self, email, name, organisation, group=None, cases=None, phone=None, request=None, **kwargs
    ):
        """
        Create a user which cannot yet log in to the system. The user is pending
        until the person validates the account and sets a password etc.
        The required attributes are the email, name and organisation for the user.
        However, optional fields for the security group (defaults to regular user), phone
        and a case spec can be provided.
        The case spec is a list of dicts in the following format,
        specifying which cases to assign the
        contact to, and if they are the primary contact for that case.
            [
                {'case': 'CASE-ID|CASE INSTANCE', 'primary': True|False}
            ]
        """
        user = None
        contact = None
        security_group_name = group or SECURITY_GROUP_ORGANISATION_USER
        # The following will raise UserExists if the user already exists
        user = self.create_base_user_model(
            email, name=name, group=security_group_name, cases=cases, phone=phone, **kwargs
        )
        user.set_unusable_password()
        user.save()
        UserProfile.objects.create(user=user)
        group = Group.objects.get(name=security_group_name)
        user.groups.add(group)
        user.assign_to_organisation(organisation, group)
        user.get_access_token()
        contact = user.contact
        contact.phone = phone
        contact.save()
        if cases:
            user.set_cases(organisation, cases, request.user)
        return user, contact

    @transaction.atomic  # noqa: C901
    def update_user(self, user_id, password=None, groups=None, **kwargs):
        """
        Update a user model
        """
        user = User.objects.get(id=user_id)
        if password:
            # Will raise Validation Error if validation fails
            validate_password(password)
            user.set_password(password)
        if "name" in kwargs:
            user.name = kwargs["name"]
        if groups:
            user.groups.clear()
            for group in get_groups(groups):
                user.groups.add(group)
        if "is_active" in kwargs:
            user.is_active = kwargs.get("is_active")
        userprofile = user.userprofile
        contact = userprofile.get_contact()
        country = kwargs.get("country") or userprofile.contact.country
        phone = kwargs.get("phone") or userprofile.contact.phone
        user_timezone = kwargs.get("timezone") or userprofile.timezone
        userprofile.timezone = pytz.timezone(user_timezone) if user_timezone else None
        userprofile.colour = kwargs.get("colour") or userprofile.colour
        userprofile.job_title_id = kwargs.get("job_title_id")
        if "set_verified" in kwargs:
            set_verified = kwargs["set_verified"]
            if set_verified == "set":
                userprofile.email_verified_at = timezone.now()
            elif set_verified == "clear":
                userprofile.email_verified_at = None
        if phone and phone != userprofile.contact.phone:
            try:
                phone = convert_to_e164(phone, country=country)
            except NumberParseException:
                pass
            contact.phone = phone
        contact.country = country
        contact.address = kwargs.get("address") or contact.address
        contact.save()
        userprofile.save()
        user.save()
        self.evaluate_sos_membership(user, groups)
        return user

    @transaction.atomic
    def create_superuser(self, email, password, **kwargs):
        """
        Creates and saves a superuser with the given email and password.
        """
        user = self.create_user(email=email.lower(), password=password, name="Super User", **kwargs)
        user.is_staff = True
        user.is_superuser = True
        UserProfile.objects.get_or_create(user=user)
        user.save()
        return user

    def get_cases(self, user, organisation=None, current=True):
        """
        Return all user cases for an organisation.
        A user can see organisation cases if they are of group Owner
        or are explicitly assigned to the case
        """
        from cases.models import Case

        kwargs = {}
        if organisation:
            kwargs["organisation"] = organisation
        if current is not None:
            kwargs["current"] = current
        return Case.objects.user_cases(user=user, **kwargs)

    def public_users(self):
        """
        Return all public users
        """
        return self.filter(groups__name__in=SECURITY_GROUPS_PUBLIC)

    def tra_users(self):
        """
        Return all TRA users
        """
        return self.filter(groups__name__in=SECURITY_GROUPS_TRA)

    def get_by_natural_key(self, username):
        """
        Override filter for username to serach for the email in case
        insensitive manner
        """
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})


class User(AbstractBaseUser, PermissionsMixin, CaseSecurityMixin):
    """
    A custom user implementation using email address as username.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True, blank=False, null=False)
    name = models.CharField(max_length=250, blank=True, null=True)
    first_name = models.CharField(max_length=30, blank=True)  # TODO: DEPRECATED
    last_name = models.CharField(max_length=30, blank=True)  # TODO: DEPRECATED
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_modified = models.DateTimeField(auto_now=True, null=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    login_code = models.CharField(max_length=50, null=True, blank=True)
    login_code_created_at = models.DateTimeField(null=True, blank=True)
    auto_assign = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        permissions = (
            ("change_org_user", "Can modify own organisation users"),
            ("can_view_all_org_cases", "Can view all cases across the Organisation"),
        )

    def delete(self, purge=False, anonymize=True):
        """
        Overriden delete method to only mark the user as deleted.
        Original hard delete is attempted if purge is True
        """
        if purge is True:
            purged = self.purge_related()
            if purged:
                return super().delete()
            else:
                raise Exception(
                    "Attempted purge failed. Related models not purged, process halted."
                )
        self.deleted_at = timezone.now()
        self.save()
        if self.anonymize:
            user, contact = self.anonymize()
            user.save()
            contact.save()
        return self

    def purge_related(self):
        """
        This method will hard delete all related models of this user.
        For safety, an explicit re-check of the ability to do so is performed first.
        I.e., no non-draft submissions created.
        Returnes True if the deletion was successful.
        """

        user_stats = self.statistics()
        if user_stats.get("non_draft_subs") == 0:
            Audit.objects.filter(created_by_id=self.id).delete()
            self.invitation_set.all().delete()
            organisation = self.organisation.organisation
            if organisation:
                self.organisation.delete()
                if len(organisation.users) == 1:
                    organisation.delete()
            return True
        return False

    def anonymize(self):
        """
        anonymize this user and related contact.
        The user and contact are not saved, but are returned
        read to be saved by the caller.
        """
        self.email = crypto.get_random_string(len(self.email))
        self.name = crypto.get_random_string(len(self.name))
        contact = self.contact
        contact.name = self.name
        contact.address = "redacted"
        contact.country = None
        contact.post_code = None
        contact.email = self.email
        contact.phone = None
        return self, contact

    @property
    def username(self):
        return self.email

    @property
    def phone(self):
        try:
            return self.contact.phone
        except Exception:
            return ""

    @property
    def country(self):
        return self.userprofile.get_contact().country

    @property
    def timezone(self):
        return self.userprofile.timezone

    @property
    def contact(self):
        try:
            return self.userprofile.get_contact()
        except Exception:
            pass

    @property
    def address(self):
        contact = self.contact
        if contact:
            return {
                "address": contact.address,
                "country": {"code": contact.country.code, "name": contact.country.name}
                if contact.country
                else {},
                "post_code": contact.post_code,
            }
        else:
            return {}

    @property
    def approved_organisations(self):
        from organisations.models import Organisation

        return list(
            Organisation.objects.select_related("organisation", "user", "security_group").filter(
                organisationuser__user=self, organisationuser__confirmed=True,
            )
        )

    @property
    def organisations(self):
        """
        All the organisations this user is a member of.
        TODO: Might be redundant, user->org is now 1-1
        """
        from organisations.models import Organisation

        return list(Organisation.objects.filter(organisationuser__user=self,))

    @property
    def organisation(self):
        """
        The organisation this user is direct employee/owner of
        """
        return self.organisationuser_set.first()

    @property
    def representing(self):
        """
        Return all organisations represented by this user
        """
        case_user = UserCase.objects.select_related("organisation",).filter(user=self)
        organisations = [cu.organisation for cu in case_user]
        return organisations + self.organisations

    def assign_to_organisation(self, organisation, group):
        from security.models import OrganisationUser

        org_user = OrganisationUser.objects.assign_user(
            organisation=organisation, user=self, security_group=group
        )
        return org_user

    def remove_from_organisation(self, organisation):
        from security.models import OrganisationUser

        org_user = OrganisationUser.objects.filter(organisation=organisation, user=self).first()
        if org_user:
            org_user.delete()
            return True
        return False

    def is_representing(self, organisation):
        """
        Check if this user is representing a given organisation in a case.
        Eequivalent to asking if this user has explicit access to the case, for that organisation
        """
        return UserCase.objects.filter(user=self, organisation=organisation).exists()

    def is_member_of(self, organisation):
        """
        Returns True if this user is a member (user) of a given organisation
        """
        return self.organisationuser_set.filter(organisation=organisation).exists()

    def is_associated_with(self, organisation):
        """
        Returns True if the user is associated with the organisation in any way,
        either by membership or representation.
        """
        return self.is_representing(organisation) or self.is_member_of(organisation)

    def toggle_role(self, role):
        """
        Toggles the given role name for this user
        """
        found_role = self.groups.filter(name=role)
        if len(found_role):
            self.groups.remove(found_role[0])
            if role == SECURITY_GROUP_ORGANISATION_OWNER and not self.groups.all():
                # A user without a group cannot log on to the public site
                # when this  function is  used to remove 'organisation owner'
                # it is safe to grant 'organisation user' instead
                self.groups.add(Group.objects.get(name=SECURITY_GROUP_ORGANISATION_USER))
        else:
            self.groups.add(Group.objects.get(name=role))

    @property
    def owner_of(self):
        """
        Return the single organisation this user is an owner of, or none
        """
        user_org = (
            self.organisationuser_set.select_related("organisation",)
            .filter(security_group__name=SECURITY_GROUP_ORGANISATION_OWNER)
            .first()
        )
        if user_org:
            return user_org.organisation
        return None

    @property
    def initials(self):
        if not hasattr(self, "_initials"):
            self._initials = "N/A"
            if self.name:
                self._initials = "".join([n[0] for n in self.name.split(" ") if n])
        return self._initials

    @property
    def colour(self):
        return self.userprofile.colour

    def generate_login_code(self):
        """
        Generate a 2FA login code
        """
        self.login_code = str(randint(10000, 99999))
        self.login_code_created_at = timezone.now()
        return self.login_code, self.login_code_created_at

    def login_code_expired(self):
        """
        Returns True if the login code has expired, False if it is still within DURATION_2FA_CODE
        setting. Returns None if there is no login code set up.
        """
        if self.login_code and self.login_code_created_at:
            return (timezone.now() - self.login_code).minutes > settings.DURATION_2FA_CODE
        return None

    def validate_login_code(self, code):
        """
        Validate a 2FA login code
        """
        return code == self.login_code and self.login_code_expired() is False

    def set_cases(self, organisation, case_specs, request_user):
        """
        Take a list of {caseid, primary} objects and update this user
        """
        from cases.models import get_case

        contact = self.contact
        if isinstance(case_specs, str):
            case_specs = json.loads(case_specs)
        for case_spec in case_specs:
            case_id = case_spec.get("case")
            case = get_case(case_spec.get("case"))
            primary = case_spec.get("primary", False)
            self.assign_to_case(case, organisation=organisation, created_by=request_user)
            contact.add_to_case(
                case, organisation=organisation, primary=primary
            )  # TODO: Note this only works for company orgs, not third party.

    @method_cache
    def is_tra(self, manager=False, with_role=None):
        """
        Returns True if this user is a TRA member.
        if manager is True, only returns true if the user is also a TRA administrator/manager.
        If with role, returns True if the user has that specific role
        """
        if with_role:
            with_role = [with_role] if isinstance(with_role, str) else with_role
            return self.groups.filter(name__in=with_role).exists()
        elif not manager:
            return self.groups.filter(name__in=SECURITY_GROUPS_TRA).exists()
        else:
            return self.groups.filter(name__in=SECURITY_GROUPS_TRA_ADMINS).exists()

    def get_full_name(self):
        """
        The user is identified by their full name and email address
        """
        return "{0} <{1}>".format(self.name, self.email)

    def get_short_name(self):
        """
        The user is identified by their email address
        """
        return self.email

    def __str__(self):
        return self.email

    def get_groups(self):
        """
        Return all the security groups the user is a member of
        """
        return Group.objects.filter(user=self)

    def has_groups(self, groups):
        return any([self.has_group(group) for group in groups])

    @method_cache
    def to_embedded_dict(self, groups=False):
        _dict = {
            "id": str(self.id),
            "name": self.name,
            "email": self.email,
            "tra": self.is_tra(),
            "initials": self.initials,
            "colour": self.colour,
            "active": self.is_active,
        }
        if groups:
            _dict["groups"] = [group.name for group in self.get_groups()]
        return _dict

    def to_minimal_dict(self):
        return {"id": str(self.id), "name": self.name}

    def to_dict(self, organisation=None, user_agent=None):
        """
        Return a JSON ready dict representation of the model.
        If the implementing class has the _to_dict method, it's output
        if used to update the core dict data
        """
        _dict = {
            "id": str(self.id),
            "created_at": self.created_at.strftime(settings.API_DATETIME_FORMAT),
            "email": self.email,
            "name": self.name,
            "initials": self.initials,
            "active": self.is_active,
            "groups": [group.name for group in self.get_groups()],
            "tra": self.is_tra(),
            "manager": self.is_tra(manager=True),
            "should_two_factor": self.should_two_factor(user_agent),
            "representing": [
                representing.to_embedded_dict()
                for representing in self.representing
                if representing
            ],
            "permissions": self.permission_map,
            **self.address,
        }
        # TODO: There is a duplication here between this code and the userprofile following
        # Is this needed? why? seems to be validating an organisation...
        if organisation:
            user_org = self.organisationuser_set.filter(
                organisation=organisation, user=self
            ).first()
            _dict["organisation"] = {
                "id": str(organisation.id),
                "name": organisation.name,
                "role": user_org.to_embedded_dict() if user_org else {},
            }
        # some system users might not have a profile
        try:
            _dict.update(self.userprofile.to_dict())
        except Exception as exc:
            logger.error("Cannot expand user profile", exc_info=True)
        return _dict

    def get_cases(self, organisation=None):
        """
        Return all user cases for the organisation
        """
        return User.objects.get_cases(user=self, organisation=organisation)

    def assign_to_case(self, case, created_by=None, organisation=None):
        """
        Assign a case to this user
        """
        from cases.models import get_case

        case = get_case(case)
        case.assign_user(
            self, created_by=created_by, relax_security=True, organisation=organisation
        )
        return case

    def remove_from_case(self, case_id, created_by=None, representing_id=None):
        """
        Remove a user from a case
        """
        from cases.models import Case

        case = Case.objects.get(id=case_id)
        case.remove_user(
            self, created_by=created_by, relax_security=True, organisation_id=representing_id
        )
        return case

    @transaction.atomic
    def load_attributes(self, attrs):
        user_keys = ["name", "email"]
        contact_keys = ["phone", "country_code"]
        profile_keys = ["timezone", "colour", "contact"]
        for key in user_keys:
            if attrs.get(key):
                setattr(self, key, attrs[key])
        self.save()
        try:
            profile = self.userprofile
        except Exception:
            profile = UserProfile.objects.create(user=self)
        for key in profile_keys:
            if attrs.get(key):
                setattr(profile, key, attrs[key])
        if not profile.contact:
            contact = profile.get_contact()
            contact.country = (
                attrs.get("country_code") or self.organisation.organisation.country.code
            )
            contact.phone = convert_to_e164(attrs.get("phone"), contact.country.code)
            contact.save()
        profile.save()
        # Sync the contact details
        for key in user_keys:
            if attrs.get(key):
                setattr(profile.contact, key, attrs[key])
        return self, profile

    def get_user_colour(self):
        """
        Derive a colour for this user.
        A test for this

        for user in User.objects.all().order_by('created_at'):
            print(user.get_user_colour())

        """
        try:
            user_count = (
                User.objects.select_related("userprofile",)
                .filter(userprofile__isnull=False, created_at__lt=self.created_at)
                .count()
            )
            total_colours = len(SAFE_COLOURS)
            index = user_count % total_colours
            return SAFE_COLOURS[index]
        except Exception:
            return DEFAULT_USER_COLOUR

    @property
    def two_factor(self):
        """
        Gets or create a 2FA record for this user
        """
        twofactor, _ = TwoFactorAuth.objects.get_or_create(user=self)
        return twofactor

    def should_two_factor(self, user_agent=None):
        """
        Return True if this user should 2FA (or if 2FA is disabled via ENABLE_2FA system parameter)
        2FA would occur if the last validation time has lapsed or unset, or if a new user
        agent is introduced.
        Note: The public front end will force 2fa for each login.
        """
        if not SystemParameter.get("ENABLE_2FA", True):
            return False
        twofactor = self.two_factor
        user_agent = user_agent or twofactor.last_user_agent
        return (
            not twofactor.last_validated
            or user_agent != twofactor.last_user_agent
            or (timezone.now() - twofactor.last_validated).days
            > settings.TWO_FACTOR_VALIDITY_PERIOD
        )

    def get_access_token(self):
        """
        Returns the user's auth token or create one if missing
        """
        try:
            auth_token = self.auth_token
        except Token.DoesNotExist:
            token = Token.objects.create(user=self)
            auth_token = token.key
        return auth_token

    def get_all_permissions(self):
        """
        Return all user permissions,
        either directly associated or indirectly via it's security group
        """
        return set(Permission.objects.filter(user=self)).union(
            set(Permission.objects.filter(group__user=self))
        )

    @property
    def permission_map(self):
        permissions = self.get_all_permissions()
        return {perm.codename: perm.name for perm in permissions}

    @property
    def organisation_users(self):
        """Return all organisation users for this user's organisation

        Returns:
            list -- User models
        """

        org_users = OrganisationUser.objects.filter(
            organisation=self.organisation.organisation, user__deleted_at__isnull=True
        ).values_list("user", flat=True)
        return org_users

    def get_setting(self, key, default=None):
        try:
            return self.userprofile.get_setting(key, default)
        except UserProfile.DoesNotExist:
            return default

    def set_setting(self, key, value):
        try:
            self.userprofile.set_setting(key, value)
            return True
        except UserProfile.DoesNotExist:
            return False

    def statistics(self):
        """
        Return some statistics about the user in regards to data created.
        The data is used to determine if the user can be hard-deleted.
        """
        from cases.models import Submission

        user_cases = [uc.case for uc in self.usercase_set.all()]
        user_stats = {
            "participating_cases": [{"id": str(case.id), "name": case.name} for case in user_cases],
            "cases_created": self.case_created_by.count(),
            "submissions_created": self.submission_created_by.count(),
            "documents": self.document_created_by.count(),
            "member_of": self.organisationuser_set.count(),
            "non_draft_subs": self.submission_created_by.filter(
                status__draft=False, status__default=False
            ).count(),
        }
        user_stats["interacted_cases"] = (
            Submission.objects.filter(case__in=user_cases).exclude(created_by=self).count()
        )
        return user_stats


class UserProfile(models.Model):
    """
    Additional information about a user.
    A user is also associated with a contact.
    NOTE: If an existing user is following an invite process,
    the invite contact might be replaced with the
    user's one, or alternatively merged.
    This is not yet implemented as invites are not direct-to-case at the moment.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    job_title = models.ForeignKey(JobTitle, null=True, blank=True, on_delete=models.PROTECT)
    timezone = TimeZoneField(null=True, blank=True)
    contact = models.OneToOneField(
        "contacts.Contact",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="userprofile",
    )
    colour = models.CharField(max_length=8, null=True, blank=True)
    email_verify_code = models.CharField(max_length=250, null=True, blank=True)
    email_verify_code_last_sent = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    last_modified = models.DateTimeField(auto_now=True)
    settings = fields.JSONField(default=dict)

    def __str__(self):
        return "{0}".format(self.user.get_full_name())

    def to_dict(self):
        country = self.contact.country if self.contact and self.contact.country else None
        _dict = {
            "country": country.name if country else None,
            "contact": self.contact.to_dict() if self.contact else None,
            "country_code": country.code if country else None,
            "phone": self.contact.phone if self.contact else None,
            "address": self.contact.address if self.contact else None,
            "email_verified_at": self.email_verified_at.strftime(settings.API_DATETIME_FORMAT)
            if self.email_verified_at
            else None,
            "email_verify_code_last_sent": self.email_verify_code_last_sent.strftime(
                settings.API_DATETIME_FORMAT
            )
            if self.email_verify_code_last_sent
            else None,
            "timezone": str(self.timezone) if self.timezone else None,
            "colour": self.colour,
            "job_title": {"id": self.job_title.id, "name": self.job_title.name}
            if self.job_title
            else None,
            # todo: We don't need this - esp if we don't allow multiple orgs/user
            "organisations": [orguser.to_embedded_dict() for orguser in self.organisations],
        }
        return _dict

    @property
    def all_organisations(self):
        from organisations.models import Organisation

        return list(Organisation.objects.filter(organisationuser__user=self.user))

    @property
    def organisations(self):
        from security.models import OrganisationUser

        return (
            OrganisationUser.objects.select_related("organisation", "user", "security_group",)
            .filter(user=self.user)
            .distinct("organisation")
        )

    def get_contact(self):
        """
        Return a contact for this userprofile or create one if it doesn't exist
        """
        if self.contact:
            return self.contact
        else:
            from contacts.models import Contact

            contact = Contact.objects.create(name=self.user.name, email=self.user.email,)
            self.contact = contact
            self._disable_audit = True
            self.save()
            return contact

    def verify_email(self):
        if (
            not self.email_verify_code
            or self.last_modified
            + datetime.timedelta(minutes=settings.EMAIL_VERIFY_CODE_REGENERATE_TIMEOUT)
            < timezone.now()
        ):
            self.email_verify_code = crypto.get_random_string(64)
            self.email_verify_code_last_sent = timezone.now()
            self.email_verified_at = None
            self.save()
        template_id = SystemParameter.get("NOTIFY_VERIFY_EMAIL")
        context = {
            "name": self.user.name,
            "verification_link": f"{settings.PUBLIC_ROOT_URL}/email/verify/?code={self.email_verify_code}",  # noqa: E501
        }
        send_report = send_mail(self.user.email, context, template_id)
        return send_report

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.save()


class TwoFactorAuth(models.Model):
    """
    Hold the required information for a user's 2FA authentication.
    Each user can have a single record in this model's data table.
    When attempts fail after n times (defined in settings.TWO_FACTOR_ATTEMPTS), the
    mechanism is locked for the duration specified in settints.TWO_FACTOR_LOCK_MINUTES
    """

    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    code = models.CharField(max_length=16, null=True, blank=True)
    last_validated = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    last_user_agent = models.CharField(max_length=1000, null=True, blank=True)
    locked_until = models.DateTimeField(null=True, blank=True)
    attempts = models.SmallIntegerField(default=0)

    def __str__(self):
        return f"{self.user} last validated at {self.last_validated}"

    def lock(self):
        self.locked_until = timezone.now() + datetime.timedelta(
            minutes=settings.TWO_FACTOR_LOCK_MINUTES
        )
        self.attempts = 0
        self.save()

    def is_locked(self):
        return self.locked_until and self.locked_until > timezone.now()

    def fail(self):
        self.attempts += 1
        if self.attempts > settings.TWO_FACTOR_ATTEMPTS:
            self.lock()
        self.save()

    def success(self, user_agent=None):
        self.last_validated = timezone.now()
        self.last_user_agent = user_agent
        self.attempts = 0
        self.save()

    def validate(self, code):
        """
        validate a code given is the same as generated and not expired.
        """
        return code == self.code and self.code_duration < (
            settings.TWO_FACTOR_MINUTES_CODE_VALID * 60
        )

    @property
    def code_duration(self):
        """
        Return the current code's life duration in seconds
        """
        duration = 0
        if self.generated_at:
            duration = (timezone.now() - self.generated_at).seconds
        return duration

    def generate_code(self, user_agent=None):
        """
        Generate a new code and reset the last_validated date.
        """
        if self.attempts == 0 or self.code_duration >= (
            settings.TWO_FACTOR_MINUTES_CODE_VALID * 60
        ):
            self.code = str(randint(10000, 99999))
            self.last_user_agent = user_agent
            self.last_validated = None
            self.generated_at = timezone.now()
            self.save()
        return self.code

    def two_factor_auth(self, user_agent=None, delivery_type=None):
        """
        Perform the full 2fa delivery either by sms (default) or email
        """
        delivery_type = delivery_type or "sms"
        if delivery_type != "email" and not self.user.phone:
            delivery_type = "email"
        code = self.generate_code(user_agent=user_agent)
        context = {"code": code}
        send_report = None
        if delivery_type == "sms":
            template_id = SystemParameter.get("2FA_CODE_MESSAGE")
            phone = self.user.phone
            send_report = send_sms(phone, context, template_id, country=self.user.country.code)
        elif delivery_type == "email":
            template_id = SystemParameter.get("PUBLIC_2FA_CODE_EMAIL")
            send_report = send_mail(self.user.email, context, template_id)
        return send_report


class PasswordResetManager(models.Manager):
    def validate_code(self, code, validate_only=False):
        """
        Validate a reset request code.
        The code is made of a user's uuid and a unique 64 char code separated with an exclamation.
        Once acknowledged, the code becomes useless, even if the user did not complete the password
        reset process.
        Returns the reset model if it validates ok
        """
        user_id, code = code.split("!")
        reset = self.filter(
            user__id=user_id,
            code=code,
            created_at__gte=timezone.now()
            - datetime.timedelta(hours=settings.PASSWORD_RESET_CODE_AGE_HOURS),
            ack_at__isnull=True,
            invalidated_at__isnull=True,
        ).first()
        if reset:
            if not validate_only:
                reset.ack_at = timezone.now()
                reset.invalidated_at = timezone.now()
                reset.save()
            return reset
        else:
            return False

    def reset_request(self, email):
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None, None
        self.filter(user=user, ack_at__isnull=True, invalidated_at__isnull=True).update(
            invalidated_at=timezone.now()
        )
        reset = self.create(user=user)
        reset.ack_at = None
        reset.invalidated_at = None
        reset.generate_code()
        send_report = reset.send_reset_link()
        return reset, send_report

    def password_reset(self, code, new_password):
        """
        Performs a password reset if the code validates ok
        Raises ValidationError if the password does not pass the min requirements
        """
        validate_password(new_password)
        reset = self.validate_code(code)
        if reset:
            user = reset.user
            user.set_password(new_password)
            user.save()
            return user
        else:
            return None


class PasswordResetRequest(models.Model):
    """
    This model holds password reset requests.
    The password reset is requested for an email address. if the request
    made is for a valid user's email, the user will be associated and the request
    will be accepted.
    A user can request many password resets although only the last one is valid.
    If existing un-acknowledged reset requests exist they will be invalidated.
    """

    user = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE)
    code = models.CharField(max_length=250, null=False, blank=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ack_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)

    objects = PasswordResetManager()

    def __str__(self):
        return f"{self.user} @ {self.created_at}"

    def generate_code(self):
        """
        Generate a new code and reset the last_validated date.
        """
        self.code = crypto.get_random_string(64)
        self.save()
        return self.code

    @property
    def age_days(self):
        return (timezone.now() - self.created_at).days

    def get_link(self):
        if self.user.is_tra():
            return f"{settings.CASEWORKER_ROOT_URL}/accounts/password/reset/{self.user.id}!{self.code}/"  # noqa: E501
        else:
            return f"{settings.PUBLIC_ROOT_URL}/accounts/password/reset/{self.user.id}!{self.code}/"

    def send_reset_link(self):
        template_id = SystemParameter.get("NOTIFY_RESET_PASSWORD")
        context = {
            "code": self.code,
            "name": self.user.name,
            "password_reset_link": self.get_link(),
        }
        send_mail(self.user.email, context, template_id)
        return True


class SystemParameter(models.Model):
    """
    > SystemParameter.get('APPLICATION_TEMPLATE_DOCUMENTS')
    > [<Document: Application-dumping-countervailing-2 (2).docx>,
       <Document: tr-doc1.odt>]
    > SystemParameter.get('DEFAULT_CASE_NAME')
    > 'Default Case'

    """

    key = models.CharField(max_length=100, null=False, blank=False)
    data_type = models.CharField(
        max_length=20,
        null=False,
        blank=False,
        default="str",
        choices=[
            ("str", "String"),
            ("list", "List"),
            ("dict", "Dictionary"),
            ("int", "Number"),
            ("bool", "Boolean"),
        ],
    )
    value = fields.JSONField(null=True, blank=True)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.PROTECT)
    editable = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.key}={self.value}"

    def get_value(self, default=None):
        """Return the value of this system parameter, cast to the right data type

        Keyword Arguments:
            default {any} -- Default value (default: {None})

        Returns:
            any -- the parameter value
        """
        if self.data_type == "list":
            if self.content_type and self.value:
                return [self.content_type.get_object_for_this_type(id=val) for val in self.value]
            else:
                return self.value or []
        elif self.value and self.data_type == "str" and self.content_type:
            return self.content_type.get_object_for_this_type(id=self.value)
        else:
            return default if self.value is None else self.value

    def set_value(self, value):
        """Sets the value of this system parameters, casting it to the right data type

        Arguments:
            value {any} -- the value to assign to the system parameter
        """
        if self.data_type == "list" and not isinstance(value, list):
            self.value = [value]
        elif self.data_type == "dict" and isinstance(value, str):
            self.value = json.loads(value)
        elif self.data_type == "bool":
            self.value = True if value in TRUTHFUL_INPUT_VALUES else False
        elif self.data_type == "int":
            try:
                self.value = int(value)
            except:
                self.value = 0
        else:
            self.value = value

    def to_dict(self, user=None):
        value = self.get(self.key, user=user)
        if self.content_type and isinstance(value, list) and value and hasattr(value[0], "to_dict"):
            value = [val.to_dict() for val in value]
        elif self.content_type and hasattr(value, "to_dict"):
            value = value.to_dict()
        return {
            "key": self.key,
            "value": value,
            "raw_value": self.value,
            "data_type": self.data_type,
            "editable": self.editable,
            "content_type": self.content_type.model if self.content_type else None,
        }

    @staticmethod
    def get(key, default=None, user=None):
        """Get a system parameter value. If an environment variable exists
        with the same name prefixed with SP_ it will be used instead.

        Arguments:
            key {str} -- The system param key to get
            default{any} -- A default value if none is set
            user{User} -- If a User model is provided, check it's settings for an override first

        Keyword Arguments:
            default {any} -- Default value (default: {None})

        Returns:
            any -- The system parameter value
        """
        try:
            override_value = None
            sysparam = SystemParameter.objects.get(key=key.upper())
            if user:
                override_value = user.get_setting(key, os.environ.get(f"SP_{key.upper()}"))
            else:
                override_value = os.environ.get(f"SP_{key.upper()}")
            if override_value:
                sysparam.set_value(override_value)
        except SystemParameter.DoesNotExist:
            if not default:
                logger.warning("SystemParameter key not found: %s", key)
            return default
        return sysparam.get_value(default=default)

    @staticmethod
    def load_parameters(param_spec):
        """
        Loads a system param spec, similiar to the one
        defined in ./system/parameters.json.
        Returns a tuple of (created, updated, removed)
        """
        count_updated = 0
        count_created = 0
        count_removed = 0
        for load_object in param_spec:
            this_object = None
            remove = load_object.get("remove")
            try:
                # load this param based on the key
                this_object = SystemParameter.objects.get(key=load_object["key"])
                if remove is True:
                    this_object.delete()
                    this_object = None
                    count_removed += 1
                else:
                    count_updated += 1
            except SystemParameter.DoesNotExist:
                # create a new key using the default value if available
                if not remove:
                    this_object = SystemParameter.objects.create(
                        key=load_object["key"],
                        data_type=load_object.get("data_type", "str"),
                        value=load_object.get("default"),
                        editable=load_object.get("editable", False),
                        content_type=load_object.get("content_type"),
                    )
                    count_created += 1
            if this_object:
                if "value" in load_object:
                    # valud exists so we'll update the value
                    this_object.set_value(load_object["value"])
                    this_object.save()
                if "editable" in load_object and load_object["editable"] != this_object.editable:
                    # allow updates to the editable state only
                    # if it is different than what is currently set.
                    this_object.editable = load_object["editable"]
                    this_object.save()
        return count_created, count_updated, count_removed
