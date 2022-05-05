from axes.backends import AxesBackend
from axes.exceptions import AxesBackendPermissionDenied
from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_credentials, toggleable

from core.services.auth.exceptions import AxesLockedOutException


class CustomAxesBackend(AxesBackend):
    @toggleable
    def authenticate(
            self, *args, **kwargs
    ):
        try:
            return super().authenticate(*args, **kwargs)
        except AxesBackendPermissionDenied:
            # The user is locked out,
            # raise exception so that we can pass it back to the caseworker/public
            raise AxesLockedOutException()
