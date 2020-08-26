import hashlib
from django.core.cache import cache
from django.conf import settings


def md5_checksum(*args, **kwargs):
    md5 = hashlib.md5()
    for arg in args:
        if arg:
            md5.update(str(arg).encode("utf8"))
    return md5.hexdigest()


def method_cache(method):
    def wrapper(instance, *args, **kwargs):
        try:
            last_mod = instance.last_modified.timestamp()
        except AttributeError:
            last_mod = "-"
        cache_key = md5_checksum(
            method.__qualname__, instance.id, last_mod, *args, *kwargs.values()
        )
        return_value = cache.get(cache_key)
        if return_value is None:
            return_value = method(instance, *args, **kwargs)
            cache.set(cache_key, return_value, 60 * settings.METHOD_CACHE_DURATION_MINUTES)
        return return_value

    return wrapper
