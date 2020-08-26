import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    help = "Generate S3 credentials file"

    def handle(self, *args, **options):
        print("Creating AWS S3 Credentials file")
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
        print("Done.")
