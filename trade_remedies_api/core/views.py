from django.http import HttpResponse

from .healthcheck import application_service_health


def health_check(_request):
    """
    Following specifications
    A view that returns the health status of the trs api app as a XML response.

    Returns:
        HttpResponse: An XML response with a 'status' field that is either 'OK' if
        application is healthy or 'Error' if there is a problem with the application. The response
        has a status code of 200 if healthy, and 503 if there is an issue.
        The response also has cache control headers set to 'no-cache, no-store, must-revalidate'.
    """

    html = application_service_health()

    if "OK" in html:
        response = HttpResponse(html, content_type="text/xml", status=200)
    else:
        response = HttpResponse(html, content_type="text/xml", status=503)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
