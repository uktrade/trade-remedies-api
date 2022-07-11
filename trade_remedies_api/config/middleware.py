from django.conf import settings
from sentry_sdk import set_user

from core.services.exceptions import AccessDenied


class ApiTokenSetter:
    """
    Allows using a request query parameter called access_token instead of the header based
    authorization token. If used, and the HTTP_AUTHRIZATION header is not present, the
    access_token query parameter will be used to set the header for the request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if "Authorization" not in request.META and "HTTP_AUTHORIZATION" not in request.META:
            token = None
            if request.GET.get("access_token"):
                token = request.GET.get("access_token")
            elif request.POST.get("access_token"):
                token = request.POST.get("access_token")
            request.META["HTTP_AUTHORIZATION"] = "Token %s" % (str(token))
        response = self.get_response(request)
        return response


# TODO-TRV2 consider if this is required, no different from origin having a
#  trusted token, seems superfluous.
class OriginValidator:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.META.get("X-Origin-Environment") in settings.ALLOWED_ORIGINS:
            return self.get_response(request)
        else:
            raise AccessDenied("Access denied. Required headers missing.")


class SentryContextMiddleware:
    """
    Sets sentry context during each request/response so we can identify unique users
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if request.user.is_authenticated:
            set_user({"id": str(request.user.id)})
        else:
            set_user(None)
        return None
