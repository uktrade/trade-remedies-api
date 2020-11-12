import logging

from core.models import SystemParameter
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Set system param content type to the right values"

    def handle(self, *args, **options):
        logger.info("+ Updating System parameter's content types")
        doc_type = ContentType.objects.get(app_label="documents", model="document")
        SystemParameter.objects.filter(
            key__in=["NOTICE_OF_INITIATION_DOCUMENT", "APPLICATION_TEMPLATE_DOCUMENTS",]
        ).update(content_type=doc_type)
