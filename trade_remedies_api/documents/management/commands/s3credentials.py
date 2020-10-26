import logging
import os
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Generate S3 credentials file"

    def handle(self, *args, **options):
        logger.info("Creating AWS S3 Credentials file")
        if not os.path.exists(os.path.expanduser("~/.aws")):
            os.mkdir(os.path.expanduser("~/.aws"))
        s3_secret = os.environ.get("S3_STORAGE_SECRET")
        s3_access_key = os.environ.get("S3_STORAGE_KEY")
        config = """[default]
output = json
region = eu-west-1
        """
        credentials = f"""[default]
aws_access_key_id = {s3_access_key}
aws_secret_access_key = {s3_secret}
        """
        with open(os.path.expanduser("~/.aws/config"), "w") as configfile:
            configfile.write(config.strip())
        with open(os.path.expanduser("~/.aws/credentials"), "w") as credentialsfile:
            credentialsfile.write(credentials.strip())
        logger.info("Completed S3 creds file generation.")
        logger.info(f"Created file path is {os.path.expanduser('~/.aws')}")
