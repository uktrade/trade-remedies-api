from security.utils import create_groups, assign_group_permissions
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    help = "Reset all security groups and their permission assignments"

    def handle(self, *args, **options):
        print("+ Asserting all groups")
        create_groups()
        print("+ Assigning permissions to groups")
        assign_group_permissions()
