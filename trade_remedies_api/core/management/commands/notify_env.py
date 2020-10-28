import logging

from core.models import SystemParameter
from core.notifier import get_client
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Generate system parameters holding references to notify template ids, based on the notify environment"

    def handle(self, *args, **options):
        logger.info("+ Getting all templates")
        client = get_client()
        templates = client.get_all_templates()
        for template in templates.get("templates", []):
            template_name = template.get("name")
            template_id = template.get("id")
            if template_name.startswith("TR_"):
                sys_param_name = template_name[3:]
                logger.info(f"    {template_name} -> {sys_param_name}")
                try:
                    sysparam = SystemParameter.objects.get(key=sys_param_name)
                    if sysparam.value != template_id:
                        logger.info(f"        Changing from {sysparam.value} to {template_id}")
                        sysparam.value = template_id
                        sysparam.save()
                except SystemParameter.DoesNotExist:
                    logger.info(f"    {sys_param_name} does not already exist.")
            else:
                logger.info(f"Template {template_name} deviates from TR_ naming convention")
