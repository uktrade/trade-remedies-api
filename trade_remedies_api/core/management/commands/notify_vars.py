import logging

from core.notifier import get_client
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Show all keys currently used across all notify templates"

    def handle(self, *args, **options):
        client = get_client()
        templates = client.get_all_templates()
        vars = {}
        keys = set([])
        for template in templates.get("templates", []):
            template_name = template.get("name")
            personalisation = template.get("personalisation")
            for key in personalisation:
                vars.setdefault(template_name, set([]))
                vars[template_name].add(key)
                keys.add(key)
        logger.info("-" * 80)
        logger.info("All keys: ")
        logger.info(", ".join(keys))
        logger.info("-" * 80)
        logger.info("By Template")
        for template_key in vars:
            logger.info(f"+ {template_key}: ")
            logger.info(f"        {', '.join(vars[template_key])}")
