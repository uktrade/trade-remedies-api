import logging

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group

from core.models import User

from security.constants import (
    SECURITY_GROUP_ORGANISATION_USER,
)

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "user_email",
            help="User's email address",
            nargs='+',
            type=str,
        )

    def handle(self, *args, **options):
        logger.info("+ Checking users")

        # check that the user exist
        for user_email in options['user_email']:
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
            # find the group in organisation user
            org = OrganisationUser.objects.filter(user_id=user_id).first()
            group_type = org.security_group.name
            if org:
                user_obj.groups.add(org.security_group)
                user_obj.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully set {user_email} as {group_type}."
                        )
                    )
            else:
                pass

        # if a group has been passed as argument, use it

        # otherwise, find the group in organisationuser
        # check the group assigned to the user in organisationuser

        # if this does not exist, ask to provide a group
        pass

        # if not password:
        #     self.stdout.write(
        #         self.style.ERROR(
        #             "Please supply a password for this test user"
        #         )
        #     )
        #     return

