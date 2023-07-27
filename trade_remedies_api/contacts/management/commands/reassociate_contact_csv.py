import csv

from django.core.management import BaseCommand
from django.db import transaction

from contacts.models import Contact
from organisations.models import Organisation


class Command(BaseCommand):
    help = """Command to loop through a csv and associate Contacts with an Organisation. Some are
    missing this association as they were created either by mistake or a long time ago.

    csv format - note the delimiter is an asterix *not* a comma to avoid needless escaping:
    contact_id*organisation_name

    arguments:
    -f, --file_path: REQUIRED - path to csv file to read from
    -d, --dry: OPTIONAL - dry run - don't commit anything to the database,
    just output potential changes
    """

    def add_arguments(self, parser):
        parser.add_argument("-f", "--file_path", nargs="?", type=str, help="File path")
        parser.add_argument("-d", "--dry", nargs="?", type=bool, help="Dry run", default=False)

    def handle(self, *args, **options):
        file_path = options["file_path"]
        dry_run = options["dry"]

        failed_associations = []
        successfully_associated_counter = 0

        with transaction.atomic():
            with open(file_path) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter="*")
                for row in csv_reader:
                    try:
                        contact_object = Contact.objects.get(pk=row[0])
                        organisation_object = Organisation.objects.get(name__iexact=row[1])

                        if contact_object.organisation:
                            # the contact already has an organisation associated with it, pass
                            failed_associations.append(
                                {
                                    "contact_id": contact_object.id,
                                    "contact_name": contact_object.name,
                                    "contact_email": contact_object.email,
                                    "organisation_name": contact_object.organisation.name,
                                    "organisation_id": organisation_object.id,
                                    "reason": "Contact already has organisation associated with it",
                                }
                            )
                        else:
                            # let's do this!
                            contact_object.organisation = organisation_object
                            contact_object.save()

                            self.stdout.write(
                                f"Contact {contact_object.email} has been assigned "
                                f"to {organisation_object.name}"
                            )
                            successfully_associated_counter += 1

                    except (Contact.DoesNotExist, Organisation.DoesNotExist):
                        failed_associations.append(
                            {
                                "contact_id": row[0],
                                "organisation_name": row[1],
                                "reason": "Contact or Organisation does not exist",
                            }
                        )
                    except Organisation.MultipleObjectsReturned:
                        failed_associations.append(
                            {
                                "contact_id": row[0],
                                "organisation_name": row[1],
                                "organisation_matches": Organisation.objects.filter(
                                    name__iexact=row[1]
                                ).values_list("id", flat=True),
                                "reason": "Multiple organisations with the same name",
                            }
                        )

            # print results
            print(f"Successfully associated {successfully_associated_counter} contacts")
            print("--------------------------------------------------------------")
            print(f"Failed to associate {len(failed_associations)} contacts")
            print(failed_associations)

            # rollback if dry run
            if dry_run:
                print("Dry run, rolling back")
                raise Exception("Dry run, rolling back")
