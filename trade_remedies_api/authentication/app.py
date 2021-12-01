"""Trade Remedies Authentication.

Trade Remedies Authentication Application configuration.
"""
from django.apps import AppConfig


class AuthConfig(AppConfig):
    name = 'authentication'
    label = 'authentication'
    verbose_name = 'Authentication Application'
