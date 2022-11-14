from typing import Any, Optional, List, Union

from django.core.management.base import BaseCommand, CommandParser

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

        parser.add_argument('--date_from', action='store')
        parser.add_argument('--date_to', action='store')

    def handle(self, *args: Any, **options: Any) -> Optional[str]:
        """
        _summary_:
            Command to receive regular reports on key metrics relating to the TRS

            e.g usage:
                $ python manage.py trs_kpis --date_from 2012-12-12 --date_to 2013-12-12

        _options_:
            date_to:    ->   YYYY-MM-DD
            date_from:  ->   YYYY-MM-DD
        """

        date_range: Union[List[str], None]

        if options['date_from'] and options['date_to']:
            date_range = (options['date_from'], options['date_to'],)

            public_users_count = UserProfile.objects.filter(email_verified_at__isnull=False, user__created_at__range=date_range, user__groups__name__in=SECURITY_GROUPS_PUBLIC).count()
            case_accepted_count = Case.objects.filter(initiated_at__isnull=False, created_at__range=date_range).count()
            case_submitted_count = Case.objects.filter(submitted_at__isnull=False, created_at__range=date_range).count()
            submission_count = Submission.objects.filter(created_at__range=date_range).count()
            files_uploaded_by_public_user_count = SubmissionDocument.objects.select_related("created_by").filter(created_by__groups__name__in=SECURITY_GROUPS_PUBLIC, created_at__range=date_range).count()
        else:
            public_users_count = UserProfile.objects.filter(email_verified_at__isnull=False, user__groups__name__in=SECURITY_GROUPS_PUBLIC).count()
            case_accepted_count = Case.objects.filter(initiated_at__isnull=False).count()
            case_submitted_count = Case.objects.filter(submitted_at__isnull=False).count()
            submission_count = Submission.objects.all().count()
            files_uploaded_by_public_user_count = SubmissionDocument.objects.select_related("created_by").filter(created_by__groups__name__in=SECURITY_GROUPS_PUBLIC).count()

        # since this value increments on a single section in the database
        # we will have to call this query without the ability for date range fetch

        total_docs_download_count = sum([doc.downloads for doc in SubmissionDocument.objects.all()])

        self.stdout.write("----------------- Result All Time ----------------")
        self.stdout.write(self.style.SUCCESS(f'Verified Public user count: {public_users_count}'))
        self.stdout.write(self.style.SUCCESS(f'Case Registration request count: {case_submitted_count}'))
        self.stdout.write(self.style.SUCCESS(f'Case applications accepted count: {case_accepted_count}'))
        self.stdout.write(self.style.SUCCESS(f'Submissions count: {submission_count}'))
        self.stdout.write(self.style.SUCCESS(f'Files uploaded by public users count: {files_uploaded_by_public_user_count}'))
        self.stdout.write(self.style.SUCCESS(f'Total files downloaded: {total_docs_download_count}'))
