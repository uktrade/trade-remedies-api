import logging

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group

from core.models import User

from security.constants import SECURITY_GROUP_ORGANISATION_USER

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "user_email",
            help="User's email address",
            nargs="+",
            type=str,
        )

    help = (
        f"Fix the error on public portal 'Invalid access to environment',  "
        f"caused by not having a group security assigned. "
        f"The command gives {SECURITY_GROUP_ORGANISATION_USER} "
        f"authorization to the user. "
        f"Pass the user email as parameter."
    )

    def handle(self, *args, **options):

        # check that the user exist
        for user_email in options["user_email"]:
            logger.info(f"Patching user {user_email}")
            normalised_email = user_email.lower().strip()
            user_obj = User.objects.filter(email__iexact=normalised_email).first()
            if not user_obj:
                raise CommandError(f"User with email '{user_email}' does not exist.")
            user_id = user_obj.id
            group_queryset = user_obj.groups.all()

            # check that the users does not have a group assigned
            if group_queryset.count():

                raise CommandError(f"User with email '{user_email}' has already a group assigned.")

            # assign 'Organisation User'
            group_obj = Group.objects.filter(name=SECURITY_GROUP_ORGANISATION_USER).first()

            if group_obj:
                user_obj.groups.add(group_obj)
                user_obj.save()
                msg = f"Successfully set {user_email} as {SECURITY_GROUP_ORGANISATION_USER}."
                logger.info(msg)

                self.stdout.write(self.style.SUCCESS(msg))
            else:
                raise CommandError(
                    f"Security group '{SECURITY_GROUP_ORGANISATION_USER}' not defined."
                )
