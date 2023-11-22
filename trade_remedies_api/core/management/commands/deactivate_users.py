import logging

from core.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Management command to deactivate users.
    """

    help = "Command to deactivate users."

    def add_arguments(self, parser):
        parser.add_argument(
            "--emails", type=str, help="CSV list of user emails", required=True
        )

    def handle(self, *args, **options):
        logging.info("Deactivating users")

        user_email_list = options["emails"].split(",")

        qs = User.objects.filter(email__in=user_email_list, is_active=True)

        qs.update(is_active=False)
        newline = "\n"
        logging.info(
            f"Deactivated Users:{newline}{newline.join([email for email in user_email_list])}"
        )
