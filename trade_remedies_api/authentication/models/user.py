import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin, Group, Permission
from django_countries.fields import CountryField
from django.db import models, transaction
from django.utils import timezone

from phonenumber_field.modelfields import PhoneNumberField

from authentication.models.two_factor_auth import TwoFactorAuth


class UserManager(BaseUserManager):
    """User Manager.

    Custom User Model Manager.
    """
    @classmethod
    def normalize_email(cls, email: str) -> str:
        """Normalise email override.

        Lowercase entire email address.
        """
        return BaseUserManager.normalize_email(email).lower()

    def get_by_natural_key(self, username: str) -> "User":
        """Get user by email.

        Override filter, get by username case insensitively.
        """
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})

    @transaction.atomic
    def create_user(self, email: str, password: str = None, **kwargs: dict) -> "User":
        """Create User.

        Create and save a User with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')
        user = self.model(email=self.normalize_email(email))
        user.two_factor = TwoFactorAuth(user=user).save()
        user.set_password(password)
        user.save()
        return user

    @transaction.atomic
    def create_superuser(self, email: str, password: str = None, **kwargs: dict) -> "User":
        """Create Super User.

        Creates and saves a superuser with the given email and password.
        """
        user = self.create_user(email, password=password)
        user.is_superuser = True
        user.save()
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """User Model.

    Custom user implementation. Assumptions are as follows:
    - Username is the user's email address which is globally unique.
    - Name, address and country are mandatory.
    - Phone number in E164 format, optional and globally unique.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    address = models.TextField()
    country = CountryField(blank_label="Select a Country")
    phone = PhoneNumberField(blank=True, null=True, unique=True)
    is_active = models.BooleanField(default=False)
    last_login = models.DateTimeField(default=timezone.now)
    date_joined = models.DateTimeField(default=timezone.now)
    # groups and user_permission fields override PermissionsMixin fields.
    # Necessary because fields.E304 is raised due to duplicate reverse accessor
    # of V1 user model. Take out when V1 custom user removed.
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="group_users",
        related_query_name="user"
    )
    user_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="permission_users",
        related_query_name="user",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    def __str__(self):
        """String representation of User."""
        return self.email

    @property
    def username(self):
        return self.email

    @property
    def is_admin(self):
        return self.is_superuser
