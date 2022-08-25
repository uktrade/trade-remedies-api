import csv
import os

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from cases.models import Submission
from organisations.models import Organisation


class Command(BaseCommand):
    help = "Command to fix the incorrect organisation data that was getting confused with " \
           "registration data"

    @transaction.atomic
    def handle(self, *args, **options):
        csv_file = os.path.join(os.path.dirname(settings.BASE_DIR), "correct_names.csv")
        with open(csv_file) as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                current_name = row[0]
                new_name = row[1]

                # First rename all of the organisation objects
                organisation_objects = Organisation.objects.filter(name=current_name)
                for org in organisation_objects:
                    org.name = new_name
                    self.stdout.write(
                        f"Organisation {current_name} updated to {new_name}"
                    )
                    org.save()

                # Then rename the Submission objects as they still (unfortunately) reference an
                # organisation_name in a separate field, rather than through FK
                submission_objects = Submission.objects.filter(organisation_name=current_name)
                for s_org in submission_objects:
                    s_org.name = new_name
                    self.stdout.write(
                        f"Submission org_name {current_name} updated to {new_name}"
                    )
                    s_org.save()
