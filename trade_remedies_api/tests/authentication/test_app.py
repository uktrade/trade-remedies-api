from django.apps import apps as django_apps


def test_app_config():
    app = django_apps.get_app_config("authentication")
    assert app.name == "authentication"
    assert app.label == "authentication"
    assert app.verbose_name == "Authentication Application"
