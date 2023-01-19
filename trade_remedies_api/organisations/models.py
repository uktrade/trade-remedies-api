import re
import logging
import uuid
import typing
from django.conf import settings
from django.db import models, transaction, connection
from core.base import BaseModel
from core.models import SystemParameter
from core.notifier import notify_footer, notify_contact_email
from core.tasks import send_mail
from audit import AUDIT_TYPE_NOTIFY
from security.models import OrganisationCaseRole, OrganisationUser, get_security_group, UserCase
from cases.models.submission import Submission
from contacts.models import Contact, CaseContact
from functools import singledispatch
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER
from organisations.constants import NOT_IN_CASE_ORG_CASE_ROLES
from core.utils import (
    sql_get_list,
    public_login_url,
)
from django_countries.fields import CountryField
from django.utils import timezone
from cases.constants import TRA_ORGANISATION_ID


logger = logging.getLogger(__name__)


@singledispatch
def get_organisation(organisation):
    return organisation


@get_organisation.register(str)
@get_organisation.register(uuid.UUID)
def _(organisation):
    try:
        return Organisation.objects.get(id=organisation)
    except Organisation.DoesNotExist:
        return None


class OrganisationManager(models.Manager):
    @transaction.atomic
    def find_similar_organisations(self, limit=None):
        """
        Perform a similarity check on organisation names
        """
        limit = float(limit or 0.5)
        _SQL = f"""
            SELECT set_limit({limit});
            SELECT similarity(o1.name, o2.name) AS score, o1.name, o2.name
            FROM organisations_organisation o1 JOIN organisations_organisation o2
            ON o1.name != o2.name AND o1.name % o2.name
            WHERE o1.duplicate_of_id is null and o2.duplicate_of_id is null;
        """  # noqa
        with connection.cursor() as cursor:
            cursor.execute(_SQL)
            rows = cursor.fetchall()
        return rows

    @transaction.atomic  # noqa: C901
    def merge_organisation_records(
        self, organisation, merge_with=None, parameter_map=None, merged_by=None, notify=False
    ):
        """
        Merge two organisations records into one.
        parameter_map is a map of fields that need to be copied from the merge_with object
        """
        from contacts.models import Contact
        from invitations.models import Invitation

        results = []
        results.append(
            Submission.objects.filter(organisation=merge_with).update(organisation=organisation)
        )
        results.append(
            Contact.objects.filter(organisation=merge_with).update(organisation=organisation)
        )
        results.append(
            Invitation.objects.filter(organisation=merge_with).update(organisation=organisation)
        )
        results.append(
            OrganisationName.objects.filter(organisation=merge_with).update(
                organisation=organisation
            )
        )
        # transfer usercases after finding clashes
        sql = f"""select uc2.id from security_usercase uc1 join security_usercase uc2
            on uc1.organisation_id='{organisation.id}'
            and uc2.organisation_id = '{merge_with.id}'
            and uc1.case_id=uc2.case_id and uc1.user_id=uc2.user_id
            """
        clash_list = sql_get_list(sql)
        try:
            results.append(
                UserCase.objects.filter(organisation=merge_with)
                .exclude(id__in=clash_list)
                .update(organisation=organisation)
            )
        except Exception as e:
            raise ValueError("Same user has access to same case on behalf of both organisations")

        # transfer case_org_contacts after finding clashes
        sql = f"""select cc2.id from contacts_casecontact cc1 join contacts_casecontact cc2
            on cc1.organisation_id='{organisation.id}'
            and cc2.organisation_id = '{merge_with.id}'
            and cc1.case_id=cc2.case_id and cc1.contact_id=cc2.contact_id
            """
        clash_list = sql_get_list(sql)
        try:
            results.append(
                CaseContact.objects.filter(organisation=merge_with)
                .exclude(id__in=clash_list)
                .update(organisation=organisation)
            )
        except Exception as e:
            raise ValueError("Same contact is in both organisations")

        # Migrate cases (caseroles)
        clash_cases = {}
        for org_case in OrganisationCaseRole.objects.filter(organisation=organisation):
            clash_cases[org_case.case.id] = org_case
        for org_case in OrganisationCaseRole.objects.filter(organisation=merge_with):
            clash = clash_cases.get(org_case.case.id)
            if clash:
                if org_case.role.key not in NOT_IN_CASE_ORG_CASE_ROLES:
                    if (
                        clash.role.key not in NOT_IN_CASE_ORG_CASE_ROLES
                        and org_case.role.key != clash.role.key
                    ):
                        # Argh, both orgs are in the same case with different,
                        # non awaiting roles - blow up!
                        raise ValueError(
                            "Cannot merge as organisations have different roles in a case",
                            org_case.case.name,
                        )
                    # Pick the best possible role for the merged org
                    clash.role = org_case.role
                    clash.save()
                clash_cases[org_case.case.id] = org_case
                org_case.delete()
        results.append(
            OrganisationCaseRole.objects.filter(organisation=merge_with).update(
                organisation=organisation
            )
        )

        results.append(
            OrganisationUser.objects.filter(organisation=merge_with).update(
                organisation=organisation
            )
        )
        updated = False
        for parameter, source in parameter_map.items():
            if source == "p2":
                setattr(organisation, parameter, getattr(merge_with, parameter))
                updated = True
        if updated:
            organisation.merged_from = merge_with
            organisation.save()
        # Notify the admins of the organisation of the merge.
        if notify and merged_by:
            notify_template_id = SystemParameter.get("NOTIFY_ORGANISATION_MERGED")
            # any baseline context can be set here.
            context = {
                "footer": notify_footer(notify_contact_email()),
                "public_cases": SystemParameter.get("LINK_TRA_CASELIST"),
            }
            self.notify_owners(
                organisation=organisation,
                template_id=notify_template_id,
                context=context,
                notified_by=merged_by,
            )
        # soft delete the merged organisation
        merge_with.delete()
        return results

    def notify_owners(self, organisation, template_id, context, notified_by):
        audit_kwargs = {
            "audit_type": AUDIT_TYPE_NOTIFY,
            "user": notified_by,
        }
        owners = organisation.organisationuser_set.filter(
            user__is_active=True, user__groups__name="Organisation Owner"
        )
        for owner in owners:
            user = owner.user
            context["full_name"] = user.name
            context["organisation_name"] = organisation.name
            audit_kwargs["model"] = user.contact
            context["login_url"] = public_login_url()
            send_mail(user.contact.email, context, template_id, audit_kwargs=audit_kwargs)

    @transaction.atomic  # noqa: C901
    def create_or_update_organisation(
        self,
        user,
        name,
        trade_association=False,
        companies_house_id=None,
        datahub_id=None,
        address=None,
        post_code=None,
        country=None,
        organisation_id=None,
        assign_user=False,
        gov_body=False,
        case=None,
        json_data=None,
        contact_object=None,
        **kwargs,
    ):
        """
        Create or update an organisation record.
        If an organisation id is provided, it will be updated. However, if the name has changed
        a new organisation will be created (or reused if the name exists).
        The user will be made a user of the organisation only if assign_user is True. This is
        only required during organisation creation when registering a new account.
        """
        organisation = None

        if organisation_id:
            try:
                organisation = Organisation.objects.get(id=organisation_id)
            except Organisation.DoesNotExist:
                pass
        if organisation is None:
            try:
                organisations = Organisation.objects.filter(name=name, country=country)
                # we can only reuse the organisation if the user is previously associated with it
                for organisation in organisations:
                    associated = user.is_associated_with(organisation)
                    if associated:
                        break
                else:
                    raise Organisation.DoesNotExist()
            except Organisation.DoesNotExist:
                organisation = Organisation(
                    created_by=user, user_context=[user], name=name, country=country
                )
                created = True
        organisation.set_user_context(user)
        organisation.set_case_context(case)
        organisation.companies_house_id = companies_house_id or organisation.companies_house_id
        organisation.trade_association = trade_association or organisation.trade_association
        organisation.datahub_id = datahub_id or organisation.datahub_id
        organisation.address = address or organisation.address
        organisation.post_code = post_code or organisation.post_code
        organisation.country = country if country else organisation.country
        organisation.json_data = json_data if json_data else organisation.json_data
        if not organisation_id and gov_body:
            organisation.gov_body = gov_body

        for key in kwargs:
            val = kwargs[key]
            if val is not None and hasattr(organisation, key):
                setattr(organisation, key, val)
        organisation.save()
        if name and organisation.name != name:
            organisation.change_name(name)
        if assign_user:
            # assign as user if owner already exists, otherwise as owner
            user_group = get_security_group(SECURITY_GROUP_ORGANISATION_OWNER)
            existing_owner = OrganisationUser.objects.filter(
                organisation=organisation, security_group=user_group
            ).exists()
            if existing_owner:
                user_group = get_security_group(SECURITY_GROUP_ORGANISATION_USER)
            org_user = OrganisationUser.objects.assign_user(
                organisation=organisation, user=user, security_group=user_group
            )
            if contact_object:
                contact_object.organisation = organisation
                contact_object.save()
        return organisation

    def user_organisation(self, user, organisation_id=None):
        """
        Return the organisation record behind the organisation id, if the user is a direct
        user of that organisation.
        If an organisation id is not provided, return the organisation associated with this user.
        Raises a DoesNotExist if not found.
        """
        _kwargs = {"organisation__id": organisation_id} if organisation_id else {}
        org_user = OrganisationUser.objects.get(user=user, **_kwargs)
        return org_user.organisation


class Organisation(BaseModel):
    name = models.CharField(max_length=500, null=False, blank=True)
    datahub_id = models.CharField(max_length=150, null=True, blank=True)
    companies_house_id = models.CharField(max_length=50, null=True, blank=True)
    trade_association = models.BooleanField(default=False)
    gov_body = models.BooleanField(default=False)
    address = models.TextField(null=True, blank=True)
    post_code = models.CharField(max_length=16, null=True, blank=True)
    country = CountryField(blank_label="Select Country", null=True, blank=True)
    duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    vat_number = models.CharField(max_length=30, null=True, blank=True)
    eori_number = models.CharField(max_length=30, null=True, blank=True)
    duns_number = models.CharField(max_length=30, null=True, blank=True)
    organisation_website = models.CharField(max_length=100, null=True, blank=True)
    fraudulent = models.BooleanField(default=False)
    merged_from = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="merged_from_org"
    )
    json_data = models.JSONField(null=True, blank=True)
    draft = models.BooleanField(default=False)

    objects = OrganisationManager()

    class Meta:
        permissions = (("merge_organisations", "Can merge organisations"),)

    def __str__(self):
        if self.trade_association:
            return f"{self.name} (TA)"
        else:
            return self.name

    @staticmethod
    def __is_potential_duplicate_organisation(
        target_org: "Organisation", potential_dup_org: "Organisation"
    ):

        DIGITS_PATTERN = re.compile(r"[^0-9]+")
        DIGITS_ALPHA_PATTERN = re.compile(r"[^0-9a-zA-Z]+")

        target_post_code = re.sub(DIGITS_ALPHA_PATTERN, "", target_org.post_code or "").lower()
        potential_post_code = re.sub(
            DIGITS_ALPHA_PATTERN, "", potential_dup_org.post_code or ""
        ).lower()

        if target_post_code == potential_post_code:
            return True

        target_vat_number = re.sub(DIGITS_PATTERN, "", target_org.vat_number or "")
        potential_vat_number = re.sub(DIGITS_PATTERN, "", potential_dup_org.vat_number or "")

        if target_vat_number == potential_vat_number:
            return True

        target_duns_number = re.sub(DIGITS_ALPHA_PATTERN, "", target_org.duns_number).lower()
        potential_duns_number = re.sub(
            DIGITS_ALPHA_PATTERN, "", potential_dup_org.duns_number or ""
        ).lower()

        if target_duns_number == potential_duns_number:
            return True

        target_eori_number = re.sub(DIGITS_PATTERN, "", target_org.eori_number or "")
        potential_eori_number = re.sub(DIGITS_PATTERN, "", potential_dup_org.eori_number or "")

        if target_eori_number == potential_eori_number:
            return True

        return (
            target_org.name == potential_dup_org.name
            or target_org.address == potential_dup_org.address
        )

    @transaction.atomic
    def _potential_duplicate_organisations(self) -> typing.List["Organisation"]:
        """
        Returns potential identical or similar organisations simialr to
        the given organisation
        """
        # first we check which organisations contain our lookup values
        # A fuzzy search, because we can't do much manipulation of the db field values
        # until it gets to be a python object after the db query

        fields_of_interest = (
            "name",
            "address",
            "post_code",
            "vat_number",
            "eori_number",
            "duns_number",
            "organisation_website",
        )

        q_objects = models.Q()

        for field in fields_of_interest:
            value = getattr(self, field)
            if value:
                if field in ("name", "address"):
                    query = {f"{field}__exact": value}
                    q_objects |= models.Q(**query)
                else:
                    query = {f"{field}__icontains": value}
                    q_objects |= models.Q(**query)

        potential_dup_orgs = Organisation.objects.exclude(id=self.id).filter(q_objects)

        if not potential_dup_orgs:
            return potential_dup_orgs
        result = []

        # we iterate through each organisation and do
        # a granular check, then eliminate non serious potential duplicates
        # then we return serious potential duplicate organisations
        for potential_dup_org in potential_dup_orgs:
            if self.__is_potential_duplicate_organisation(self, potential_dup_org):
                result += [potential_dup_org]
        return result

    @property
    def potential_duplicate_organisations(self) -> typing.List["Organisation"]:
        return self._potential_duplicate_organisations()

    def has_role_in_case(self, case, role):
        """
        Returns True if this organisation has the requested role in the given case
        :param case: A case instance
        :param role: A CaseRole instance or name
        """
        return OrganisationCaseRole.objects.has_organisation_case_role(self, case, role)

    def get_case_role(self, case):
        """
        Return this organisation's role in a case
        """
        org_case_role = OrganisationCaseRole.objects.filter(case=case, organisation=self).first()
        if org_case_role:
            return org_case_role.role
        else:
            return None

    def assign_case(self, case, role, user=None):
        """
        Assign the organisation to a case under a given role
        :param case: A case instance
        :param role: A CaseRole instance, id or name
        """
        return OrganisationCaseRole.objects.assign_organisation_case_role(
            organisation=self, case=case, role=role, created_by=user
        )

    def related_pending_registrations_of_interest(
        self, requested_by, all_interests=True, archived=False
    ):
        """
        Return all pending registrations of interest for this organisaion.
        TODO: can reduce the api calls in CaseInterestAPI->GET
        """
        from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST

        user_filter = {
            "created_by__organisationuser__organisation": self,
        }
        if not requested_by.has_perm("core.can_view_all_org_cases") or not all_interests:
            user_filter["created_by"] = requested_by
        submissions = Submission.objects.select_related(
            "case",
            "status",
            "type",
            "organisation",
            "created_by",
        ).filter(
            type_id=SUBMISSION_TYPE_REGISTER_INTEREST,
            deleted_at__isnull=True,
            organisation__organisationcaserole__case=models.F("case"),
            organisation__organisationcaserole__organisation=self,
            organisation__organisationcaserole__approved_at__isnull=True,
            **user_filter,
        )
        if not archived:
            submissions = submissions.exclude(archived=True)
        submissions = submissions.distinct().order_by("created_at")
        return submissions

    def related_cases(self, initiated_only=True, order_by=None, requested_by=None):
        """
        Return all cases for this organisation, whether representing other companies
        or own cases.
        The result is a list of dictionaries, each with a case and org ids and names
        """
        from security.models import UserCase
        from cases.models import Case

        order_by = order_by or "organisation"
        cases = UserCase.objects.filter(
            user__organisationuser__organisation=self,
            case__deleted_at__isnull=True,
            case__archived_at__isnull=True,
        )
        if requested_by and not requested_by.has_perm("core.can_view_all_org_cases"):
            cases = cases.filter(user=requested_by)
        if initiated_only:
            cases = cases.filter(case__initiated_at__isnull=False)
        cases = cases.values("organisation_id", "case_id").distinct()
        _cache = {}
        related_cases = []
        for uc in cases:
            if uc["organisation_id"] not in _cache:
                _cache[uc["organisation_id"]] = Organisation.objects.get(id=uc["organisation_id"])
            if uc["case_id"] not in _cache:
                _cache[uc["case_id"]] = Case.objects.get(id=uc["case_id"])
            related_cases.append(
                {
                    "case": _cache[uc["case_id"]].to_embedded_dict(),
                    "organisation": _cache[uc["organisation_id"]].to_embedded_dict(),
                    "has_non_draft_subs": _cache[uc["organisation_id"]].has_non_draft_subs(
                        _cache[uc["case_id"]]
                    ),
                }
            )
        return related_cases

    def assign_user(self, user, security_group, confirmed=True):
        """
        Assign a user to this organisation
        :param user: A user instance
        :param security_group: The security group to assign the user as (name or Group instance)
        """
        return OrganisationUser.objects.assign_user(
            user=user, organisation=self, security_group=security_group, confirmed=confirmed
        )

    def get_owner(self):
        """
        Return the owner user for this organisation, if available.
        """
        return OrganisationUser.objects.filter(
            organisation=self, security_group=get_security_group(SECURITY_GROUP_ORGANISATION_OWNER)
        ).first()

    @property
    def users(self):
        """
        All users for this organisation
        """
        return OrganisationUser.objects.select_related(
            "user",
            "organisation",
            "security_group",
        ).filter(organisation=self)

    @property
    def has_users(self):
        """
        Returns True/False whether this organisation instance has any users associated with it.
        """
        return self.users.exists()

    @property
    def user_count(self):
        return self.users.count()

    def _to_dict(self, case=None, with_contacts=True):
        contacts = []
        if with_contacts:
            if case:
                contacts = self.case_contacts(case, all_contacts=not self.gov_body)
            else:
                contacts = self.contacts.filter(deleted_at__isnull=True)
        primary_contact = self.primary_contact(case)
        has_non_draft_subs = None
        if case:
            has_non_draft_subs = Submission.objects.filter(
                organisation=self, case=case, status__default=False
            ).exists()
        return {
            "name": self.name,
            "datahub_id": self.datahub_id,
            "companies_house_id": self.companies_house_id,
            "trade_association": self.trade_association,
            "address": self.address,
            "post_code": self.post_code,
            "country": {
                "name": self.country.name if self.country else None,
                "code": self.country.code if self.country else None,
            }
            if self.country
            else None,
            "contacts": [contact.to_dict(case) for contact in contacts if not contact.deleted_at],
            "primary_contact": primary_contact.to_embedded_dict() if primary_contact else None,
            "gov_body": self.gov_body,
            "is_tra": str(self.id) == TRA_ORGANISATION_ID,
            "has_non_draft_subs": has_non_draft_subs,
            "vat_number": self.vat_number,
            "eori_number": self.eori_number,
            "duns_number": self.duns_number,
            "organisation_website": self.organisation_website,
            "fraudulent": self.fraudulent,
            "previous_names": [pn.to_dict() for pn in self.previous_names]
            if self.has_previous_names
            else None,
            "merged_from_id": str(self.merged_from.id) if self.merged_from else None,
            "json_data": self.json_data if self.json_data else None,
            "users": [user.enhance_dict() for user in self.users],
        }

    def _to_embedded_dict(self, **kwargs):
        return {"id": str(self.id), "name": self.name}

    def case_contacts(self, case, all_contacts=True):
        """
        Return all contacts assosciated with the organisation for a specific case.
        These might be lawyers representing the organisation or direct employee.
        """
        case_contacts = Contact.objects.select_related("userprofile", "organisation",).filter(
            casecontact__case=case,
            casecontact__organisation=self,
            deleted_at__isnull=True,
        )
        if all_contacts:
            return case_contacts.union(self.contacts)
        else:
            return case_contacts

    def has_non_draft_subs(self, case=None):
        case = case or self.case_context
        if case:
            return (
                case
                and Submission.objects.filter(
                    organisation=self, case=case, status__default=False
                ).exists()
            )

    @property
    def has_roi(self):
        case = self.case_context
        if case:
            from cases.models import Submission

            return (
                case
                and Submission.objects.filter(
                    organisation=self, case=case, status__default=False, type__key="interest"
                ).exists()
            )

    @property
    def contacts(self):
        """
        All contacts directly associated with this organisation (employees)
        """
        contacts = (
            self.contact_set.select_related(
                "userprofile",
                "organisation",
            )
            .filter(deleted_at__isnull=True)
            .order_by("created_at")
        )
        return contacts

    def primary_contact(self, case=None):
        """
        Return the primary contact of the organsiation.
        """
        case = case or self.case_context

        contact = (
            self.casecontact_set.select_related("contact__userprofile", "organisation")
            .filter(
                case=case,
                primary=True,
                contact__deleted_at__isnull=True,
            )
            .first()
        )
        if contact:
            return contact.contact
        else:
            contacts = self.casecontact_set.select_related(
                "contact__userprofile", "organisation"
            ).filter(
                case=case,
                contact__deleted_at__isnull=True,
            )
            if contacts:
                return contacts[0].contact
            else:
                contacts = self.contacts
                if contacts:
                    return contacts[0]
        return contact

    def notify_approval_status(self, action, contact, values, case, sent_by):
        """
        Notify organisation contact about an approval or rejection to a case.
        """
        templates_map = {
            "approve": "NOTIFY_INTERESTED_PARTY_REQUEST_PERMITTED",
            "deny": "NOTIFY_INTERESTED_PARTY_REQUEST_DENIED",
            "change": "NOTIFY_COMPANY_ROLE_CHANGED_V2",
            "remove": "NOTIFY_COMPANY_ROLE_DENIED_V2",
        }
        template_id = templates_map.get(action)
        if template_id:
            notify_template_id = SystemParameter.get(template_id)
            audit_kwargs = {
                "audit_type": AUDIT_TYPE_NOTIFY,
                "user": sent_by,
                "case": case,
                "model": contact,
            }
            send_mail(contact.email, values, notify_template_id, audit_kwargs=audit_kwargs)
        else:
            logger.error("Invalid action for organisation notification: %s", action)

    def has_previous_names(self):
        """
        Returns True if this organisation has had a name change in the past
        """
        return self.organisationname_set.exists()

    @property
    def case_count(self):
        return len(OrganisationCaseRole.objects.case_prepared(self.id))

    @property
    def previous_names(self):
        return self.organisationname_set.all().order_by("to_date")

    def change_name(self, name):
        """
        Change an organisation name, retaining a record of the name change.
        The old name will be stored away in OrganisationName, along with the date of change.
        The new name will be assigned to the organisation.
        """
        org_name = None
        if name != self.name:
            prev_name_change = (
                OrganisationName.objects.filter(organisation=self).order_by("-to_date").first()
            )
            from_date = prev_name_change.to_date if prev_name_change else None
            to_date = timezone.now()
            org_name = OrganisationName.objects.create(
                organisation=self, name=self.name, from_date=from_date, to_date=to_date
            )
            self.name = name
            self.save()
        return org_name


class OrganisationName(models.Model):
    """
    Maintain a history of organisation name changes along with the relevant dates.
    Organisation's name will denormalise into the submission on the point of creation and will
    display the denormalised name in the public file.
    Case workers will have the history of name changes available to them where applicable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organisation = models.ForeignKey(
        Organisation, null=False, blank=False, on_delete=models.PROTECT
    )
    name = models.CharField(max_length=500, null=False, blank=False)
    from_date = models.DateTimeField(null=True, blank=True)
    to_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="%(class)s_created_by",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return f"{self.organisation}: {self.name} from {self.from_date} to {self.to_date}"

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "from_date": self.from_date.strftime(settings.API_DATETIME_FORMAT)
            if self.from_date
            else None,
            "to_date": self.to_date.strftime(settings.API_DATETIME_FORMAT)
            if self.to_date
            else None,
        }
