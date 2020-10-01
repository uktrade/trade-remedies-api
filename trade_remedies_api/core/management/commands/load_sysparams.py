import json
from core.models import SystemParameter
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):

    help = """Load system parameters. The file format is similiar to a standard fixture json with
    the following differences:
    1. `default` is used as initial value for the key if it does not exist in the database.
    2. The absence of a `value` key for a specific parameter denotes retaining existing value.
    3. The existence of a `value` key denotes updating to that value
    4. Editable state of the parameter can be updated

    Note: If a param contains the remove key as true, it will be removed from the
    database if it exists, ignored otherwise. Removed keys can be kept or removed from the file in
    future.

    By default the file used is in `core/system/parameters.json`
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default=f"{settings.SITE_ROOT}/trade_remedies_api/core/system/parameters.json",
        )

    def handle(self, *args, **options):
        print("Loading system parameters")
        path = options.get("path")
        with open(path) as json_data:
            objects = json.loads(str(json_data.read()))
        count_created, count_updated, count_removed = SystemParameter.load_parameters(objects)
        if count_updated:
            print(f"Upadted {count_updated} row(s)")
        if count_created:
            print(f"Created {count_created} row(s)")
        if count_removed:
            print(f"Removed {count_removed} rows(s)")
