import os
import pytz
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.utils import crypto
from security.utils import create_groups, assign_group_permissions
from core.models import User, UserProfile
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token


base_dir = os.path.dirname(os.path.dirname(__file__))


class Command(BaseCommand):

    help = "Create the master admin user"

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            nargs="?",
            action="store",
            type=str,
            default=os.environ.get("MASTER_ADMIN_EMAIL"),
            help="Email address",
        )
        parser.add_argument(
            "--password",
            nargs="?",
            action="store",
            type=str,
            default=os.environ.get("MASTER_ADMIN_PASSWORD"),
            help="User password [default: randomised]",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        health_check_user_email = os.environ["HEALTH_CHECK_USER_EMAIL"]
        health_check_user_token = os.environ["HEALTH_CHECK_USER_TOKEN"]
        print("|= Creating the admin user ==================|")
        print("Generating security groups")
        create_groups()
        assign_group_permissions()
        print("Setting up admin user")
        admin_users = User.objects.filter(is_staff=True, deleted_at__isnull=True)
        if len(admin_users) == 0:
            user = User.objects.create_superuser(
                options["email"], options["password"], country="GB", timezone="Europe/London"
            )
            user.groups.add(Group.objects.get(name="Super User"))
            user.is_staff = True
            user.save()
            print("Admin user created")
        elif len(admin_users) > 1:
            print("Multiple admin users exist!")
        else:
            print("Admin user already exists. Resetting password")
            admin_user = admin_users[0]
            admin_user.set_password(options["password"])
            admin_user.save()
        print("|= Creating the health check user ==================|")
        health_user = User.objects.filter(email=health_check_user_email, deleted_at__isnull=True)
        if len(health_user) == 0:
            user = User.objects.create(
                name="Health Check",
                email=health_check_user_email,
                password=crypto.get_random_string(24),
            )
            token = Token.objects.create(user=user, key=health_check_user_token)
            print(f"Health check user created with token {health_check_user_token}")
        else:
            print(f"Health check user exists. Regenerating token as {health_check_user_token}")
            Token.objects.filter(user=health_user[0]).delete()
            Token.objects.create(user=health_user[0], key=health_check_user_token)
        print("Done.")
