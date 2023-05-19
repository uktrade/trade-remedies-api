from django.core.management.base import BaseCommand

from contacts.models import CaseContact
from organisations.models import Organisation
from organisations.services.v2.serializers import OrganisationSerializer

import json
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "List potential duplicate organisations"

    def add_arguments(self, parser):
        # Optional arguments
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

        self.stdout.write("Creating list of potential duplicate organisations")

        all_organisation_information = {}
        total_organisations_count = all_organisations.count()
        for index, organisation in enumerate(all_organisations):
            print(f"Processing organisation {index + 1} of {total_organisations_count}")

            # get list of potential organisations
            organisation_information = {
                "name": organisation.name,
                "address": organisation.address,
                "post code": organisation.post_code,
                "registration number": organisation.companies_house_id,
                "country": organisation.country.code,
            }

            merge_record = organisation.find_potential_duplicate_orgs(fresh=True)
            potential_duplicates = merge_record.potential_duplicates()
            organisation_information["number_of_duplicates"] = len(potential_duplicates)
            organisation_information["potential_duplicates"] = [
                {"id": str(each.child_organisation.id), "name": each.child_organisation.name}
                for each in potential_duplicates
            ]

            cases = []
            for case_contact in CaseContact.objects.filter(contact__organisation=organisation):
                cases.append(
                    {
                        "case ID": str(case_contact.case.id),
                        "case name": case_contact.case.name,
                        "representing ID": str(case_contact.organisation.id),
                        "representing name": case_contact.organisation.name,
                    }
                )

            organisation_information["cases"] = cases
            organisation_information["number_of_case_contacts"] = len(cases)

            all_organisation_information[str(organisation.id)] = organisation_information

        with open("potential_duplicates_on_the_trs.json", "w") as json_out:
            json_dumps_str = json.dumps(all_organisation_information, indent=4)
            print(json_dumps_str, file=json_out)

        self.stdout.write(
            self.style.SUCCESS(
                "Potential duplicates list created, saved at 'potential_duplicates_on_the_trs.json'"
            )
        )
