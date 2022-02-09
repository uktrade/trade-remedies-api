import logging
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import crypto
from security.utils import create_groups, assign_group_permissions
from core.models import User as v1_user_model, UserProfile
from authentication.models.user import User as v2_user_model
from django.contrib.auth.models import Group
from rest_framework.authtoken.models import Token

logger = logging.getLogger(__name__)

base_dir = os.path.dirname(os.path.dirname(__file__))


class Command(BaseCommand):

    help = "Migrate the auth module from v1 to v2"

    @transaction.atomic
    def handle(self, *args, **options):
        pass

        for v1u in v1_user_model.objects.all():
            if not v2_user_model.objects.filter(email=v1u.email).exist():
                new_v2_user = v2_user_model.objects.create(
                    id=v1u.id,
                    email=v1u.email,
                    name=v1u.name,
                    address=v1u.address,
                    country=v1u.country,
                    phone=v1u.phone,
                    is_active=v1u.is_active,
                    last_login=v1u.last_login,
                    date_joined=v1u.date_joined,
                )
                new_v2_userprofile = UserProfile.objects.create(
                    user=new_v2_user
                )