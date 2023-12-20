from django.core.management import BaseCommand
from django.utils import timezone

from core.models import UserProfile


class Command(BaseCommand):
    help = "Marks a user profile as email address validated - not public and only used in autotest"

    def add_arguments(self, parser):
        parser.add_argument("email_address", nargs=1, type=str)

    def handle(self, *args, **options):
        email_addresses = options["email_address"]
        for email_address in email_addresses:
            profile = UserProfile.objects.filter(user__email=email_address).first()

            if not profile:
                self.stderr.write(f"{email_address} not found")
                continue

            profile.email_verified_at = timezone.now()
            profile.save()
            self.stdout.write("\U0001F44D" + f" {email_address} ")
