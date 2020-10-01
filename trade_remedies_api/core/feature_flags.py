import os

from django.core.cache import cache

from core.models import SystemParameter


feature_flag_ttl = int(os.environ.get("FEATURE_FLAG_TTL", 5 * 60))


class FeatureFlagNotFound(Exception):
    """Raised if a feature flag does not exist."""


class FeatureFlags(object):
    """
    Maintains a cache of feature flag values.

    Usage:

        feature_flags = FeatureFlags()
        if feature_flags('my_flag'):
            # perform some conditional action.
    """

    def __init__(self):
        self._flag_map = {}

    def __call__(self, name):
        try:
            return self._flag_map[name]
        except KeyError:
            val = is_enabled(name)
            self._flag_map[name] = val
            return val


def is_enabled(name):
    """
    Evaluate if a feature is enabled.

    Feature flags are expected to be defined as SystemParameter objects of
    type `int` with a key that is upper case and prefixed with `FEATURE_`.
    A value of 1 implies the feature is enabled.
    A value of 0 implies the feature is disabled.
    """
    key = f"FEATURE_{name.upper()}"
    cache_key = f"FF:{key}"
    val = cache.get(cache_key)
    if val is None:
        sys_param = SystemParameter.get(key)
        if sys_param is None:
            raise FeatureFlagNotFound(key)
        val = sys_param > 0
        cache.set(cache_key, val, feature_flag_ttl)
    return val
