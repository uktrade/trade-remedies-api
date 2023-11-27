import logging

from core.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    """
    Management command to deactivate users.
    """

    help = "Command to deactivate users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--exclude",
            type=str,
            help="CSV list of user emails that should not be deactivated",
            required=True,
        )
        parser.add_argument(
            "--exclude_matching_string",
            type=str,
            help="Matching string to exclude",
            required=True,
        )

    def handle(self, *args, **options):
        logging.info("Deactivating users")

        user_email_list = options["exclude"].split(",")
        exclude_matching_string = options["exclude_matching_string"]

        email_filter = Q()
        for name in user_email_list:
            email_filter |= Q(name__iexact=name)

        qs = User.objects.exclude(email_filter | Q(email__icontains=exclude_matching_string))

        qs.update(is_active=False)
        newline = "\n"
        logging.info(f"Deactivated Users:{newline}{newline.join([user.email for user in qs])}")
