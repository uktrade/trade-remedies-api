from django.conf import settings
from django.http import JsonResponse


def get_rate(group, request):
    """Return the rate limit for the given user. The Health Check user does not get rate-limited."""
    if not settings.API_RATELIMIT_ENABLED:
        return None

    if request.user.is_authenticated and request.user.email == settings.HEALTH_CHECK_USER_EMAIL:
        return None

    return settings.API_RATELIMIT_RATE


def ratelimited_error(request, exception):
    """Return a 429 response when the user is rate-limited."""
    return JsonResponse({"error": "ratelimited"}, status=429)
