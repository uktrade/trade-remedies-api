"""OpenSearch functionality"""

import logging

from django.conf import settings
from opensearchpy import OpenSearch

logger = logging.getLogger(__name__)


class OSWrapperError(Exception):
    """Raised when an ES client cannot be configured"""


class OSWrapper(object):
    _os_client = None

    @classmethod
    def get_client(cls):
        """Returns an instantiated OpenSearch object. Caches result and returns cached object if already instantiated.

        If running on Production with the _VCAP_SERVICES environment variable, uses the bound OpenSearch service.
        If running locally, uses the OPENSEARCH_HOST and OPENSEARCH_PORT environment variables.
        """
        if not cls._os_client:
            logger.info("Instantiating OpenSearch client")
            if settings.OPENSEARCH_URI:
                credentials = settings.OPENSEARCH_URI
            else:
                credentials = {"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}
            cls._os_client = OpenSearch([credentials])
        return cls._os_client


def get_open_search():
    """Returns an instantiated OpenSearch object if possible, otherwise raises an OSWrapperError"""
    if settings.OPENSEARCH_URI or settings.OPENSEARCH_HOST:
        return OSWrapper.get_client()
    msg = "OpenSearch client cannot be configured - no URI or HOST setting detected"
    raise OSWrapperError(msg)
