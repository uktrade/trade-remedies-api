import logging
import geckoboard
from django.conf import settings
from reports.geckoboard.datasets import get_dataset, DATASETS
from reports.queries import REPORT_REGISTRY

logger = logging.getLogger(__name__)


def get_client():
    return geckoboard.client(settings.GECKOBOARD_API_KEY)


def dataset(key, env=None):
    env = env or settings.GECKOBOARD_ENV
    client = get_client()
    name, spec = get_dataset(key, env)
    if name and spec:
        return client.datasets.find_or_create(
            name, fields=spec.get("fields"), unique_by=spec.get("unique_by")
        )
    return None


def delete_dataset(key, env=None):
    env = env or settings.GECKOBOARD_ENV
    client = get_client()
    name, _ = get_dataset(key, env)
    return client.datasets.delete(name)


def update_geckoboard_datasets():
    """
    Update (or replace) all geckboard datasets
    """
    logger.info(f"Initiating report update for {settings.GECKOBOARD_ENV}")
    for key in DATASETS:
        logger.info(f"Report key: {key} (in registry: {key in REPORT_REGISTRY})")
        if key in REPORT_REGISTRY:
            data = REPORT_REGISTRY[key]()
            _dataset = dataset(key)
            if _dataset:
                if DATASETS[key]["mode"] == "replace":
                    result = _dataset.put(data)
                elif DATASETS[key]["mode"] == "append":
                    result = _dataset.post(data)
                if result:
                    logger.info("Dataset updated")
