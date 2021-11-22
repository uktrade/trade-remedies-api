from django.apps import AppConfig


class CasesConfig(AppConfig):
    name = "cases"

    def ready(self):
        import cases.receivers  # noqa F401
