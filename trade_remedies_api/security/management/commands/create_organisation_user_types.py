import logging

from django.core.management.base import BaseCommand

from security.groups import ORGANISATION_USER_TYPES
from security.models import OrganisationUserType

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Populate the database with the correct OrganisationUserType objects"

    def handle(self, *args, **options):
        for organisation_user_type in ORGANISATION_USER_TYPES:
            obj, created = OrganisationUserType.objects.get_or_create(
                name=organisation_user_type[0]
            )
            if created:
                logger.info(f"{obj.name} was created.")
            else:
                logger.info(f"{obj.name} already exists.")
