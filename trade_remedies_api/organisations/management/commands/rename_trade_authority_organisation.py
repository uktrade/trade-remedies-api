from django.core.management.base import BaseCommand, CommandError
from organisations.models import Organisation


class Command(BaseCommand):
    help = "Update the name of the Trade Authority organisation."

    def add_arguments(self, parser):
        parser.add_argument("old_name", type=str, help="old name of organisation")
        parser.add_argument("new_name", type=str, help="new name of organisation")

    def handle(self, *args, **options):
        try:
            trade_authority_organisation = Organisation.objects.get(name=options["old_name"])
        except Organisation.DoesNotExist:
            raise CommandError(f'No organisation found with name \'{options["old_name"]}\'.')
        except Exception as e:
            self.stdout.write(
                self.style.ERROR( str(e) )
            )
            return
        trade_authority_organisation.name = options["new_name"]
        trade_authority_organisation.save()
        self.stdout.write(
            self.style.SUCCESS(
                f'Updated Trade Authority name from \'{options["old_name"]}\' to'
                f'\'{options["new_name"]}\''
            )
        )
        return
