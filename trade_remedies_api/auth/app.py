"""Trade Remedies Auth.

Trade Remedies Auth Application configuration.
"""
from django.apps import AppConfig


class AuthConfig(AppConfig):  # noqa: D100
    name = 'trade_remedies_api.auth'
    label = 'auth'
    verbose_name = 'Auth Application'
