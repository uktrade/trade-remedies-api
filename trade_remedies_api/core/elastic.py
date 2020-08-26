import logging
from elasticsearch import Elasticsearch
from django.conf import settings


logger = logging.getLogger(__name__)


class ESWrapper(object):
    _es_client = None

    @classmethod
    def get_client(cls):
        if not cls._es_client:
            logger.info("Instantiating ElasticSearch client")
            if settings.ELASTIC_URI:
                credentials = settings.ELASTIC_URI
            else:
                credentials = {"host": settings.ELASTIC_HOST, "port": settings.ELASTIC_PORT}
            cls._es_client = Elasticsearch([credentials])
        return cls._es_client


def get_elastic():
    if settings.ELASTIC_URI or settings.ELASTIC_HOST:
        return ESWrapper.get_client()
    return None
