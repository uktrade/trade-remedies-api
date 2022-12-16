from django_countries.fields import Country
from rest_framework.utils import encoders


class JsonEncoder(encoders.JSONEncoder):
    """
    JSONEncoder subclass that knows how to encode django-country fields
    """

    def default(self, obj):
        if isinstance(obj, Country):
            return obj.alpha3 or ""
        return super().default(obj)
