from django.core.management.base import BaseCommand

from cases.tasks import process_timegate_actions


class Command(BaseCommand):

    help = "Process the timegate actions that are queued and due."

    def handle(self, *args, **options):
        print("+ Processing timegate actions")
        process_timegate_actions()
        print("+ Completed processing timegate actions")
