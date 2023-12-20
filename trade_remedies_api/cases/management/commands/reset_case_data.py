import logging

import os
from cases.models import (
    SubmissionDocument,
    Submission,
    Product,
    ExportSource,
    HSCode,
    TimeGateStatus,
    CaseWorkflowState,
    CaseWorkflow,
)
from content.models import Content
from audit.models import Audit
from notes.models import Note
from contacts.models import Contact, CaseContact
from invitations.models import Invitation
from security.models import UserCase, OrganisationUser, OrganisationCaseRole
from security.constants import SECURITY_GROUPS_TRA
from documents.models import Document, DocumentBundle
from organisations.models import Organisation, OrganisationName
from core.models import User, UserProfile
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db import connection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reset all cases data. Careful with this one as it will erase all cases."

    def handle(self, *args, **options):
        HSCode.objects.all().delete()
        TimeGateStatus.objects.all().delete()
        CaseWorkflowState.objects.all().delete()
        CaseWorkflow.objects.all().delete()
        SubmissionDocument.objects.all().delete()
        Document.objects.all().update(parent=None)
        for doc in Document.objects.all():
            doc.file.delete()
        Document.objects.all().delete()
        DocumentBundle.objects.all().delete()
        Product.objects.all().delete()
        ExportSource.objects.all().delete()
        Invitation.objects.all().delete()
        Submission.objects.filter(parent__isnull=False).delete()
        Submission.objects.all().delete()
        UserCase.objects.all().delete()
        OrganisationName.objects.all().delete()
        OrganisationUser.objects.all().delete()
        OrganisationCaseRole.objects.all().delete()
        UserProfile.objects.exclude(
            Q(user__is_staff=True)
            | Q(user__email=os.environ.get("HEALTH_CHECK_USER_EMAIL"))
            | Q(user__groups__name__in=SECURITY_GROUPS_TRA)
        ).update(contact=None)
        CaseContact.objects.all().delete()
        UserProfile.objects.exclude(
            Q(user__is_staff=True)
            | Q(user__email=os.environ.get("HEALTH_CHECK_USER_EMAIL"))
            | Q(user__groups__name__in=SECURITY_GROUPS_TRA)
        ).delete()
        Contact.objects.filter(userprofile__isnull=True).delete()
        Organisation.objects.exclude(
            id__in=["815893cb-fc21-498d-a88a-1f9bb911b030", "8850d091-e119-4ab5-9e21-ede5f0112bef"]
        ).delete()
        Note.objects.all().delete()
        Content.objects.filter(parent__isnull=False).delete()
        Content.objects.all().delete()
        Audit.objects.all().delete()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM cases_case")
        User.objects.exclude(
            Q(is_staff=True)
            | Q(email=os.environ.get("HEALTH_CHECK_USER_EMAIL"))
            | Q(groups__name__in=SECURITY_GROUPS_TRA)
        ).delete()
        logger.info("Completed reset_case_data command")
