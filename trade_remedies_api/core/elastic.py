import logging
from elasticsearch import Elasticsearch
from opensearchpy import OpenSearch
from django.conf import settings


logger = logging.getLogger(__name__)


class OSWrapperError(Exception):
    """Raised when an ES client cannot be configured"""


class OSWrapper(object):
    _os_client = None

    @classmethod
    def get_client(cls):
        if not cls._os_client:
            logger.info("Instantiating OpenSearch client")
            if settings.OPENSEARCH_URI:
                credentials = settings.OPENSEARCH_URI
            else:
                credentials = {"host": settings.OPENSEARCH_HOST, "port": settings.OPENSEARCH_PORT}
            cls._os_client = OpenSearch(
                [credentials],
                #use_ssl=True,
                verify_certs=False,
                #ssl_assert_hostname=False,
                #ssl_show_warn=False,
                #http_auth=(settings.OPENSEARCH_USERNAME, settings.OPENSEARCH_PASSWORD),
            )
        return cls._os_client


def get_open_search():
    if settings.OPENSEARCH_URI or settings.OPENSEARCH_HOST:
        return OSWrapper.get_client()
    msg = "OpenSearch client cannot be configured - no URI or HOST setting detected"
    raise OSWrapperError(msg)
