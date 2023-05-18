from django.core.management.base import BaseCommand
from organisations.models import Organisation
from organisations.services.v2.serializers import OrganisationSerializer

import json
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "List potential duplicate organisations"

    def add_arguments(self, parser):
        # Optional aruguments
        parser.add_argument(
            "--name", type=str, help='Name of organisation. E.g., "The Organisation LTD"'
        )

    def get_organisations(self, **options):
        if options["name"]:
            # Only find potential duplicates for (optionally) named organisation
            logger.info(f"Finding potential duplicates for organisation {options['name']}")
            # used 'filter' instead of 'get' to receive iterable queryset
            return Organisation.objects.filter(name=options["name"])
        else:
            logger.info("Finding potential duplicates for ALL organisations")
            # get all organisation objects
            return Organisation.objects.all()

    def handle(self, *args, **options):
        # get organisation object(s)
        all_organisations = self.get_organisations(**options)

        logger.info(f"Creating list of potential duplicate organisations")

        self.stdout.write("----- Potential duplicate organisations -----")

        all_potential_duplicates = []
        for organisation in all_organisations:
            # get list of potential organisations
            merge_record = organisation.find_potential_duplicate_orgs(fresh=True)

            # check if the organisation has potential duplicates
            if merge_record.status == "duplicates_found":
                duplicate_organisations = []
                for child in merge_record.potential_duplicates():
                    # use "OrganisationSerializer" instead of creating the dictionary manually
                    child_organisations = OrganisationSerializer(
                        instance=child.child_organisation, slim=True
                    ).data

                    # extract id and name fields for each duplicate organisation
                    duplicate_organisations.append(
                        {
                            key: value
                            for (key, value) in child_organisations.items()
                            if key == "id" or key == "name"
                        }
                    )

                # group all duplicates with 'parent' organisation - this will end up as an array in json
                all_potential_duplicates.append(
                    {
                        # json doesn't like UUIDs for keys
                        str(organisation.id): {
                            "number_of_duplicates": len(duplicate_organisations),
                            "duplicates": duplicate_organisations,
                        },
                    }
                )

        # TODO: Replace 'print' with something more suitable
        print(json.dumps(all_potential_duplicates))

        self.stdout.write(self.style.SUCCESS(f"Potential duplicates list created"))
