from axes.backends import AxesBackend
from axes.exceptions import AxesBackendPermissionDenied
from axes.helpers import toggleable

from core.services.auth.exceptions import AxesLockedOutException


class CustomAxesBackend(AxesBackend):
    """Custom Axes Authentication backend which purposefully raises an exception when a user
    is locked out, so it can be picked up and handled by the AuthenticationSerializer."""

    @toggleable
    def authenticate(self, *args, **kwargs):
        try:
            return super().authenticate(*args, **kwargs)
        except AxesBackendPermissionDenied:
            # The user is locked out,
            # raise exception so that we can pass it back to the caseworker/public
            raise AxesLockedOutException()
