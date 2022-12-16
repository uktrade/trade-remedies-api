import importlib

from django_restql.fields import NestedFieldWraper


def StringNestedField(serializer_module: str, serializer_class_name: str, *args, **kwargs):
    """Identical to django_restql NestedField except it accepts a string of the serializer class
    and it will import it within this function to avoid circular import errors"""

    serializer_class = getattr(
        importlib.import_module(f"{serializer_module}"), serializer_class_name
    )

    return NestedFieldWraper(*args, **kwargs, serializer_class=serializer_class)
