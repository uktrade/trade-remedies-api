import os

from typing import Any, Optional

from django.core.management.base import BaseCommand, CommandParser

from cases.constants import (
    SUBMISSION_STATUS_REGISTER_INTEREST_DRAFT,
    SUBMISSION_STATUS_REGISTER_INTEREST_RECEIVED,
    SUBMISSION_TYPE_APPLICATION,
    SUBMISSION_TYPE_REGISTER_INTEREST,
)
from security.constants import SECURITY_GROUPS_PUBLIC

from core.models import UserProfile
from cases.models import Case, Submission, SubmissionDocument


class Command(BaseCommand):

    help = (
        "Produce report related to key metrics relating to the TRS"
        "Accounts: Email verified public user accounts"
        "Sessions: Successful public user log-ins (in period)"
        "Case registrations requested"
        "Submissions: Case Submissions"
        "Files uploaded by public users"
        "Files downloaded by public users"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        # Named (optional) arguments

        parser.add_argument("--date_from", action="store")
        parser.add_argument("--date_to", action="store")
        parser.add_argument("--outpath", action="store")

    def handle(self, *args: Any, **options: Any) -> Optional[str]:
        """
        _summary_:
            Command to receive regular reports on key metrics relating to the TRS

            e.g usage:
                $ python manage.py trs_kpis --date_from 2012-12-12 --date_to 2013-12-12

        _options_:
            date_to:    ->   YYYY-MM-DD
            date_from:  ->   YYYY-MM-DD
            outpath:    ->   e.g. => /tmp/
        """

        if options["date_from"] and options["date_to"]:
            additional_filters = {
                "created_at__range": (
                    options["date_from"],
                    options["date_to"],
                )
            }
            user_additional_filters = {
                "user__created_at__range": additional_filters["created_at__range"]
            }
        else:
            additional_filters = {}
            user_additional_filters = {}

        public_users_count = UserProfile.objects.filter(
            email_verified_at__isnull=False,
            user__groups__name__in=SECURITY_GROUPS_PUBLIC,
            **user_additional_filters,
        ).count()

        submitted_rois = Submission.objects.filter(
            type_id=SUBMISSION_TYPE_REGISTER_INTEREST,
            status__draft=False,
            **additional_filters,
        ).count()
        accepted_rois = Submission.objects.filter(
            type_id=SUBMISSION_TYPE_REGISTER_INTEREST, status__sufficient=True, **additional_filters
        ).count()

        submitted_applications = Submission.objects.filter(
            type_id=SUBMISSION_TYPE_APPLICATION, status__draft=False, **additional_filters
        ).count()

        submission_count = Submission.objects.filter(**additional_filters).count()
        files_uploaded_by_public_user_count = (
            SubmissionDocument.objects.select_related("created_by")
            .filter(created_by__groups__name__in=SECURITY_GROUPS_PUBLIC, **additional_filters)
            .count()
        )

        # since this value increments on a single section in the database
        # we will have to call this query without the ability for date range fetch

        total_docs_download_count = sum([doc.downloads for doc in SubmissionDocument.objects.all()])

        stats = {
            "Verified Public user count": public_users_count,
            "Case registrations submitted": submitted_rois,
            "Case registrations accepted": accepted_rois,
            "Total case applications submitted": submitted_applications,
            "Submissions count": submission_count,
            "Files uploaded by public users count": files_uploaded_by_public_user_count,
            "Total files downloaded": total_docs_download_count,
        }

        self.stdout.write("----------------- Result All Time ----------------")
        for label, value in stats.items():
            self.stdout.write(self.style.SUCCESS(f"{label}: {value}"))

        if options["outpath"]:

            # add trailing backslash if it doesn't exist
            outfile_location = os.path.join(options["outpath"], "")

            with open(f"{outfile_location}outfile.txt", "a") as f:
                for label, value in stats.items():
                    f.write(f"{label}: {value}")
