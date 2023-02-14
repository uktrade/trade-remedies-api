from django.http import HttpResponse
from celery.task.control import inspect


def _pingdom_custom_status_html_wrapper(status: str, response_time: float) -> str:
    """
    response data format:
    https://documentation.solarwinds.com/en/success_center/pingdom/content/topics/http-custom-check.htm?cshid=pd-rd_115000431709-http-custom-check
    """
    html = """
    <br/>
        <pingdom_http_custom_check>
            <status>
                <strong>{}</strong>
            </status>
            <response_time>
                <strong>{}</strong>
            </response_time>
        </pingdom_http_custom_check>
    <br/>
    <br/>
    """.format(
        status, response_time
    )
    return html


def application_issue():
    return _pingdom_custom_status_html_wrapper("OK", 50)


def health_check(request):
    """
    Following specifications
    A view that returns the health status of the trs api app as a XML response.

    Returns:
        HttpResponse: An XML response with a 'status' field that is either 'OK' if
        application is healthy or 'Error' if there is a problem with the application. The response
        has a status code of 200 if healthy, and 503 if there is an issue.
        The response also has cache control headers set to 'no-cache, no-store, must-revalidate'.
    """

    html = application_issue()

    if not application_issue():
        response = HttpResponse(html, content_type="text/xml", status=200)
    else:
        response = HttpResponse(html, content_type="text/xml", status=503)
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
