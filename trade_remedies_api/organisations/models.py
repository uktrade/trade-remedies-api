import logging
import uuid
from functools import singledispatch

import django.db.models
import requests
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import connection, models, transaction
from django.db.models import F, Q, Value
from django.db.models.functions import Replace
from django.utils import timezone
from django.utils.html import escape
from django_countries.fields import CountryField

from audit import AUDIT_TYPE_NOTIFY, AUDIT_TYPE_ORGANISATION_MERGED
from audit.utils import audit_log
from cases.constants import SUBMISSION_TYPE_REGISTER_INTEREST, TRA_ORGANISATION_ID
from cases.models.submission import Submission, Submission
from contacts.models import CaseContact, CaseContact, Contact, Contact
from core.base import BaseModel
from core.models import SystemParameter
from core.notifier import notify_contact_email, notify_footer
from core.tasks import send_mail
from core.utils import public_login_url, sql_get_list
from organisations.constants import (
    AWAITING_ORG_CASE_ROLE,
    NOT_IN_CASE_ORG_CASE_ROLES,
    PREPARING_ORG_CASE_ROLE,
    REJECTED_ORG_CASE_ROLE,
)
from security.constants import SECURITY_GROUP_ORGANISATION_OWNER, SECURITY_GROUP_ORGANISATION_USER
from security.models import OrganisationCaseRole, OrganisationUser, UserCase, get_security_group

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
    def merge_organisations(
        self,
        parent_organisation,
        child_organisation,
        merge_record_object,
    ):
        """
        Merges the child_organisation into the parent_organisation, deleting the former.
        Parameters
        ----------
        parent_organisation : parent organisation that will retain its details (name..etc.)
        child_organisation : organisation to be merged - child organisation that will get swallowed into the parent
        Returns
        -------
        The parent organisation object containing the records of both organisation_a and organisation_b
        """
        from invitations.models import Invitation

        with transaction.atomic():
            # finding the users who are members of the child org, but not of the parent.
            # we need to add those users to the parent
            parent_organisation_users = [each.user for each in parent_organisation.users]
            for org_user in child_organisation.users:
                if org_user.user not in parent_organisation_users:
                    org_user.organisation = parent_organisation
                    org_user.save()
                else:
                    # the child org user is already a member of the parent org, delete
                    org_user.delete()

            # updating the UserCase objects of the child_org
            UserCase.objects.filter(organisation=child_organisation).update(
                organisation=parent_organisation
            )

            # updating the contacts, this will also update the CaseContact object
            Contact.objects.filter(organisation=child_organisation).update(
                organisation=parent_organisation
            )

            # updating all OrganisationCaseRole objects which are unique to the child organisation, and
            # to cases which the parent_organisation doesn't have a corresponding
            # OrganisationCaseRole object. If the parent org does have a corresponding OrganisationCaseRole object
            # then we will rely on the chosen_case_roles dict on the merge_record which should contain
            # the caseworkers preference, if it is not there for whatever reason, we will default to the
            # parent's role in the case
            parent_org_cases = OrganisationCaseRole.objects.filter(
                organisation=parent_organisation
            ).values_list("case_id")

            OrganisationCaseRole.objects.filter(organisation=child_organisation).exclude(
                case_id__in=parent_org_cases
            ).update(organisation=parent_organisation)

            shared_cases = OrganisationCaseRole.objects.filter(
                organisation=child_organisation
            ).filter(case_id__in=parent_org_cases)
            if shared_cases:
                for org_case_role in shared_cases:
                    if str(org_case_role.case.id) in merge_record_object.chosen_case_roles:
                        # there has been a preference selected for this case, so we will use that
                        chosen_role_id = merge_record_object.chosen_case_roles[
                            str(org_case_role.case.id)
                        ]
                        chosen_role = OrganisationCaseRole.objects.get(id=chosen_role_id)
                    else:
                        chosen_role = OrganisationCaseRole.objects.get(
                            case=org_case_role.case, organisation=parent_organisation
                        )

                    chosen_role.organisation = parent_organisation
                    chosen_role.save()

                    # now we want to delete the other org case_roles from either the parent or org to this case except for the chosen role
                    OrganisationCaseRole.objects.filter(case=org_case_role.case).filter(
                        Q(organisation=child_organisation) | Q(organisation=parent_organisation)
                    ).exclude(id=chosen_role.id).delete()

            # updating the submissions
            Submission.objects.filter(organisation=child_organisation).update(
                organisation=parent_organisation
            )

            # updating the invitations
            Invitation.objects.filter(organisation=child_organisation).update(
                organisation=parent_organisation
            )

            child_organisation.delete()

        return parent_organisation

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

    @transaction.atomic
    def _potential_duplicate_orgs(self, fresh=False) -> "OrganisationMergeRecord":
        """
        Returns potential identical or similar organisations similar to
        the given organisation.
        """

        # first we check which organisations contain our lookup values
        # A fuzzy search, because we can't do much manipulation of the db field values
        # until it gets to be a python object after the db query

        special_characters = (
            "!",
            "%",
            "-",
            "_",
            "*",
            "?",
            ":",
            ";",
            ",",
            ".",
            "/",
            "|",
            " ",
        )

        def annotate_without_special_chars(
            queryset: django.db.models.QuerySet, field: str
        ) -> (str, django.db.models.QuerySet):
            """
            Annotate a queryset with a field that has all special characters removed
            Parameters
            ----------
            queryset : the queryset to operate on
            field : the name of the field to annotate

            Returns
            -------
            tuple:
                0 - the name of the annotated column with all special characters removed
                1 - the queryset with the annotated columns
            """
            annotation_kwargs = {
                f"{field}_sf{index}": Replace(
                    field if index == 0 else f"{field}_sf{index - 1}", Value(each), Value("")
                )
                for index, each in enumerate(special_characters)
            }
            last_annotation = f"{field}_sf{len(special_characters) - 1}"
            return last_annotation, queryset.annotate(**annotation_kwargs)

        potential_duplicates = Organisation.objects.exclude(id=self.id).exclude(
            deleted_at__isnull=False
        )
        if hasattr(self, "merge_record"):
            # if there is a merge record associated with this organisation, we presume that
            # the database has been scanned for potential duplicates, and we only want to check
            # those organisations that have been created or modified since the last check. Unless
            # the fresh argument is True, in which case we will always scan for all
            if not fresh and self.merge_record.last_searched:
                potential_duplicates = potential_duplicates.filter(
                    models.Q(created_at__gte=self.merge_record.last_searched)
                    | models.Q(last_modified__gte=self.merge_record.last_searched)
                )

                # finding the existing current duplicates (if any) that have been updated since
                # the last search, we want to delete them as potential duplicates, so they
                # can be searched again (in case they have been updated since the last search
                # to no longer match as a duplicate.)
                self.merge_record.potential_duplicates().filter(
                    child_organisation__last_modified__gte=self.merge_record.last_searched
                ).delete()
            if fresh:
                # if this is a fresh search, we want to delete all existing potential duplicates
                self.merge_record.duplicate_organisations.all().delete()
        else:
            OrganisationMergeRecord.objects.create(parent_organisation=self)

        if potential_duplicates:
            q_objects = models.Q()

            # filter fields that require an exact (case-insensitive) match
            exact_match_fields = (
                "name",
                "address",
                "duns_number",
            )
            for field in exact_match_fields:
                value = getattr(self, field)
                if value:
                    query = {f"{field}__iexact": value}
                    q_objects |= models.Q(**query)

            # filter by reg_number and post_code, removing special characters
            ignore_special_character_fields = (
                "companies_house_id",
                "post_code",
            )

            for field in ignore_special_character_fields:
                value = getattr(self, field)
                if value:
                    value = "".join(c for c in value if c not in special_characters)
                    if value:
                        # making sure that the value is not empty after removing all special characters
                        removed_special_chars = annotate_without_special_chars(
                            potential_duplicates,
                            field,
                        )
                        potential_duplicates = removed_special_chars[1]
                        query = {f"{removed_special_chars[0]}__iexact": value}
                        q_objects |= models.Q(**query)

            # now we filter by the VAT number and EORI number
            ignore_alpha_character_fields = (
                "vat_number",
                "eori_number",
            )
            for field in ignore_alpha_character_fields:
                value = getattr(self, field)
                if value:
                    value = "".join(c for c in value if c.isdigit())
                    if value:
                        # making sure that the value is not empty after removing all non-digit characters
                        removed_special_chars = annotate_without_special_chars(
                            potential_duplicates,
                            field,
                        )
                        potential_duplicates = removed_special_chars[1]
                        query = {f"{removed_special_chars[0]}__icontains": value}
                        q_objects |= models.Q(**query)

            # now we filter by the URL, removing http://, www., and the suffix
            if url := self.organisation_website:
                url = url.split("/")
                if url[0] in ["https:", "http:"]:
                    url = url[2].split(".")
                else:
                    url = url[0].split(".")
                # now we iterate through the reversed URL list and find the domain
                for i in range(len(url) - 1, 0, -1):
                    if url[i] in ["co", "uk", "com", "net", "org"]:
                        continue
                    else:
                        url_domain = url[i]
                        q_objects |= models.Q(organisation_website__icontains=url_domain)
                        break

            # applying the filter to the queryset
            potential_duplicates = potential_duplicates.filter(q_objects)

        # Why did the cow cross the road? To get to the udder side.
        # lol.
        if potential_duplicates:
            # there are new potential duplicates
            # now we update the merge record and create DuplicateOrganisationMerge records for each
            # of the confirmed duplicates (if they don't already exist)
            for potential_dup_org in potential_duplicates:
                DuplicateOrganisationMerge.objects.get_or_create(
                    merge_record=self.merge_record, child_organisation=potential_dup_org
                )
            self.merge_record.status = "duplicates_found"

            # change any existing complete merge records to not started
            self.merge_record.submissionorganisationmergerecord_set.filter(
                status="complete"
            ).update(status="not_started")
        elif self.merge_record.duplicate_organisations.filter(status="pending").exists():
            # there are existing, unresolved potential duplicates, we
            # want to update the merge record
            self.merge_record.status = "duplicates_found"
            self.merge_record.submissionorganisationmergerecord_set.filter(
                status="complete"
            ).update(status="in_progress")
        else:
            self.merge_record.status = "no_duplicates_found"

        self.merge_record.last_searched = timezone.now()
        self.merge_record.save()
        return self.merge_record

    def find_potential_duplicate_orgs(self, fresh=False) -> "OrganisationMergeRecord":
        return self._potential_duplicate_orgs(fresh=fresh)

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
            "name": escape(self.name),
            "datahub_id": self.datahub_id,
            "companies_house_id": escape(self.companies_house_id),
            "trade_association": self.trade_association,
            "address": escape(self.address),
            "post_code": escape(self.post_code),
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
            "vat_number": escape(self.vat_number),
            "eori_number": escape(self.eori_number),
            "duns_number": escape(self.duns_number),
            "organisation_website": escape(self.organisation_website),
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
        contact_filter = ["userprofile", "organisation"]
        case_contacts = Contact.objects.select_related(*contact_filter).filter(
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

    def representative_cases(self) -> list:
        """
        Returns all cases where this organisation is acting as a representative.

        Returns a list of dictionaries where each dictionary contains the details of a particular
        representation on a case:

        [
            {
                'case': CaseSerializer.data,  # the case they are on
                'role': 'domestic_producer',   # the role they are acting as
                'on_behalf_of': 'interested_party_organisation_name',  # the organisation they are acting on behalf of
                'validated': True,  # whether the representation has been validated
                'validated_at': '2020-01-01T00:00:00Z',  # when the representation was validated
            },
            ...
        ]
        """
        from cases.services.v2.serializers import CaseSerializer
        from invitations.models import Invitation

        representations = []

        representative_case_contacts = (
            CaseContact.objects.filter(
                contact__organisation=self,
            )
            .exclude(contact__organisation=F("organisation"))
            .distinct("case")
        )
        for case_contact in representative_case_contacts:
            try:
                corresponding_org_case_role = OrganisationCaseRole.objects.get(
                    organisation=case_contact.organisation, case=case_contact.case
                )
            except OrganisationCaseRole.DoesNotExist:
                continue
            representation = {
                "on_behalf_of": case_contact.organisation.name,
                "on_behalf_of_id": case_contact.organisation.id,
                "case": CaseSerializer(case_contact.case).data,
                "role": corresponding_org_case_role.role.name,
            }
            # now we need to find if this case_contact has been created as part of an ROI or an invitation
            invitation = (
                Invitation.objects.filter(
                    contact__organisation=self,
                    case=case_contact.case,
                    organisation=case_contact.organisation,
                    invitation_type=2,
                    approved_at__isnull=False,
                )
                .order_by("-last_modified")
                .first()
            )
            if invitation:
                representation.update(
                    {"validated": invitation.approved_at, "validated_at": invitation.approved_at}
                )
                representations.append(representation)
            else:
                # maybe it's an ROI that got them here
                try:
                    (
                        Submission.objects.filter(
                            type_id=SUBMISSION_TYPE_REGISTER_INTEREST,
                            contact__organisation=self,
                            case=case_contact.case,
                            organisation=case_contact.organisation,
                        )
                        .order_by("-last_modified")
                        .first()
                    )
                    representation.update(
                        {
                            "validated": bool(corresponding_org_case_role.validated_at),
                            "validated_at": corresponding_org_case_role.validated_at,
                        }
                    )
                    representations.append(representation)
                except Submission.DoesNotExist:
                    ...
                    # todo - log error here, how do they have access to this case

        return representations

    def rejected_cases(self) -> list:
        """Returns all cases where this organisation has been rejected as either an interested
        party or a representative.

        Returns a list of dictionaries where each dictionary contains the details of a particular
        rejection from a case:

        [
            {
                'case': CaseSerializer.data,  # the case they were rejected from
                'date_rejected': '2021-01-01T00:00:00Z',  # when they were rejected
                'rejected_by': UserSerializer.data,  # who rejected them
                'rejected_reason': 'Fraudulent',  # the reason they were rejected
                'type': 'interested_party/representative',  # whether they were rejected as an interested party or a representative
            },
            ...
        ]
        """
        from cases.services.v2.serializers import CaseSerializer
        from core.services.v2.users.serializers import UserSerializer
        from invitations.models import Invitation

        rejections = []

        # finding the rep invitations for this org which have been rejected
        rejected_invitations = Invitation.objects.filter(
            contact__organisation=self,
            rejected_by__isnull=False,
            rejected_at__isnull=False,
            invitation_type=2,  # only rep invites
        )
        for invitation in rejected_invitations:
            rejections.append(
                {
                    "case": CaseSerializer(
                        invitation.submission.case, fields=["name", "reference"]
                    ).data,
                    "date_rejected": invitation.rejected_at,
                    "rejected_reason": invitation.submission.deficiency_notice_params.get(
                        "explain_why_contact_org_not_verified", ""
                    ),
                    "rejected_by": UserSerializer(
                        invitation.rejected_by, fields=["name", "email"]
                    ).data,
                    "type": "representative",
                }
            )

        # finding the interested party cases for this org which have been rejected
        rejected_org_case_roles = OrganisationCaseRole.objects.filter(
            organisation=self, role__key="rejected"
        )
        for rejected_org_case_role in rejected_org_case_roles:
            rejections.append(
                {
                    "case": CaseSerializer(
                        rejected_org_case_role.case, fields=["name", "reference"]
                    ).data,
                    "date_rejected": rejected_org_case_role.validated_at,
                    "rejected_reason": "N/A",
                    "rejected_by": UserSerializer(
                        rejected_org_case_role.validated_by, fields=["name", "email"]
                    ).data,
                    "type": "interested_party",
                }
            )

        return rejections

    def does_name_match_companies_house(self) -> bool:
        """
        Returns True if the organisation name matches the name on Companies House, False otherwise.
        """
        from core.services.ch_proxy import COMPANIES_HOUSE_BASE_DOMAIN, COMPANIES_HOUSE_BASIC_AUTH

        if registration_number := self.companies_house_id:
            if organisation_name := self.name:
                headers = {"Authorization": f"Basic {COMPANIES_HOUSE_BASIC_AUTH}"}
                response = requests.get(
                    f"{COMPANIES_HOUSE_BASE_DOMAIN}/company/{registration_number}",
                    headers=headers,
                )
                if response.status_code == 200:
                    if (
                        response.json().get(
                            "company_name",
                        )
                        == organisation_name
                    ):
                        return True
        return False

    def organisation_card_data(self) -> dict:
        """
        Returns a dictionary containing the data required to render the organisation card on the
        front-end.
        """
        from organisations.services.v2.serializers import (
            OrganisationSerializer,
            OrganisationCaseRoleSerializer,
        )
        from core.services.v2.users.serializers import UserSerializer

        return_dict = {}

        # get the slim, quick OrganisationSerializer data

        return_dict.update(
            OrganisationSerializer(
                self,
                fields=[
                    "name",
                    "companies_house_id",
                    "organisation_website",
                    "a_tag_website_url",
                    "country",
                    "full_country_name",
                    "vat_number",
                    "duns_number",
                    "eori_number",
                    "address",
                    "post_code",
                    "country_name",
                ],
            ).data
        )

        representative_cases = self.representative_cases()
        return_dict["representative_cases"] = representative_cases
        return_dict["approved_representative_cases"] = [
            each for each in representative_cases if each["validated"]
        ]

        rejected_cases = self.rejected_cases()
        return_dict["rejected_cases"] = rejected_cases
        return_dict["rejected_representative_cases"] = [
            each for each in rejected_cases if each["type"] == "representative"
        ]
        return_dict["rejected_interested_party_cases"] = [
            each for each in rejected_cases if each["type"] == "interested_party"
        ]

        return_dict["approved_organisation_case_roles"] = [
            OrganisationCaseRoleSerializer(each, exclude=["organisation"]).data
            for each in self.organisationcaserole_set.all()
            if each.role.key
            not in [AWAITING_ORG_CASE_ROLE, REJECTED_ORG_CASE_ROLE, PREPARING_ORG_CASE_ROLE]
        ]

        return_dict["does_name_match_companies_house"] = self.does_name_match_companies_house()

        return_dict["users"] = [
            UserSerializer(each.user, exclude=["contact", "organisation"]).data
            for each in self.organisationuser_set.all()
        ]

        return return_dict

    def get_identical_fields(self, other_organisation: "Organisation") -> list:
        """
        Returns a list of fields which are identical between this organisation and the other
        organisation.
        """
        identical_fields = []

        for field in self._meta.get_fields():
            if field.name in [
                "id",
                "created_at",
                "updated_at",
                "created_by",
                "updated_by",
                "country",
            ]:
                continue
            parent_value = getattr(self, field.name, None)
            child_value = getattr(other_organisation, field.name, None)
            if parent_value and child_value and parent_value == child_value:
                identical_fields.append(field.name)

        return identical_fields

    def get_user_cases(self, exclude_rejected=True):
        """Return all UserCases for this organisation except for those with the rejected role if
        exclude_rejected is True."""
        user_cases = UserCase.objects.filter(
            user__organisationuser__organisation=self,
            case__deleted_at__isnull=True,
            case__archived_at__isnull=True,
        )

        if exclude_rejected:
            exclude_ids = []
            for user_case in user_cases:
                if OrganisationCaseRole.objects.filter(
                    case=user_case.case,
                    organisation__organisationuser__user=user_case.user,
                    role__key=REJECTED_ORG_CASE_ROLE,
                ).exists():
                    exclude_ids.append(user_case.id)
            user_cases = user_cases.exclude(id__in=exclude_ids)

        return user_cases


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


class OrganisationMergeRecord(BaseModel):
    status_choices = (
        ("not_checked", "Not checked"),
        ("no_duplicates_found", "No duplicates found"),
        ("duplicates_found", "Duplicates found"),
    )
    id = None
    status = models.CharField(choices=status_choices, default="not_checked", max_length=30)
    parent_organisation = models.OneToOneField(
        Organisation, on_delete=models.PROTECT, related_name="merge_record", primary_key=True
    )
    submission = models.ManyToManyField(
        Submission, related_name="merge_records", through="SubmissionOrganisationMergeRecord"
    )
    last_searched = models.DateTimeField(null=True)
    chosen_case_roles = models.JSONField(null=True, blank=True)

    def merge_organisations(
        self,
        organisation=None,
        notify_users=False,
        create_audit_log=False,
    ) -> "Organisation":
        """
        Merges the duplicate organisations into the parent organisation.
        Parameters
        ----------
        organisation : the parent organisation to merge the duplicates into
        notify_users : True if you want the users to be notified of the merge
        create_audit_log : True if you want to create an audit log of the merge

        Returns
        -------
        Organisation
        """
        if not organisation:
            organisation = self.parent_organisation

        ids_merged = []
        for potential_duplicate_organisation in self.potential_duplicates().filter(
            status="attributes_selected"
        ):
            # going through the potential duplicates and applying the attributes from each
            # duplicate selected by the caseworkers to the draft organisation
            potential_duplicate_organisation._apply_selections(
                organisation=organisation,
            )

            # now we finally run the merge_organisations method to re-associate the child
            # objects (UserCase, OrganisationUser, OrganisationCaseRole...etc.) with the
            # draft organisation
            Organisation.objects.merge_organisations(
                organisation, potential_duplicate_organisation.child_organisation, self
            )
            ids_merged.append(potential_duplicate_organisation.child_organisation.id)

        """if notify_users:
            notify_template_id = SystemParameter.get("NOTIFY_ORGANISATION_MERGED")
            for organisation_user in organisation.organisationuser_set.filter(
                security_group__name=SECURITY_GROUP_ORGANISATION_OWNER
            ):
                send_mail(
                    organisation_user.user.email,
                    context={
                        "full_name": organisation_user.user.name,
                        "organisation_name": organisation.name,
                        "login_url": public_login_url(),
                        "public_cases": SystemParameter.get("LINK_TRA_CASELIST"),
                    },
                    template_id=notify_template_id,
                    audit_kwargs={
                        "audit_type": AUDIT_TYPE_NOTIFY,
                        "user": organisation_user.user,
                    },
                )"""
        if create_audit_log:
            audit_log(
                audit_type=AUDIT_TYPE_ORGANISATION_MERGED,
                model=self,
                data={"organisations_merged_with": ids_merged},
            )

        return organisation

    def potential_duplicates(self):
        return self.duplicate_organisations.order_by("-created_at")


class DuplicateOrganisationMerge(BaseModel):
    status_choices = (
        ("pending", "Pending"),
        ("confirmed_not_duplicate", "Not duplicate"),
        ("confirmed_duplicate", "Confirmed duplicate"),
        ("attributes_selected", "Attributes selected"),
    )
    merge_record = models.ForeignKey(
        OrganisationMergeRecord, on_delete=models.CASCADE, related_name="duplicate_organisations"
    )
    child_organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, related_name="potential_duplicate_organisations"
    )
    status = models.CharField(choices=status_choices, default="pending", max_length=30)
    parent_fields = ArrayField(models.CharField(max_length=500), null=True, blank=True)
    child_fields = ArrayField(models.CharField(max_length=500), null=True, blank=True)

    def _apply_selections(self, organisation=None):
        if not organisation:
            organisation = self.merge_record.parent_organisation

        if self.status == "attributes_selected":
            if self.parent_fields:
                for field in self.parent_fields:
                    setattr(
                        organisation, field, getattr(self.merge_record.parent_organisation, field)
                    )
            if self.child_fields:
                for field in self.child_fields:
                    setattr(organisation, field, getattr(self.child_organisation, field))

            organisation.save()
        return organisation


class SubmissionOrganisationMergeRecord(BaseModel):
    status_choices = (
        ("not_started", "Not started"),
        ("in_progress", "In Progress"),
        ("complete", "Complete"),
    )

    id = None
    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, primary_key=True)
    organisation_merge_record = models.ForeignKey(OrganisationMergeRecord, on_delete=models.CASCADE)
    status = models.CharField(default="not_started", choices=status_choices, max_length=30)
