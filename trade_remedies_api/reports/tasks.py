from celery import shared_task
from reports.geckoboard.base import update_geckoboard_datasets


@shared_task()
def update_geckoboard():
    update_geckoboard_datasets()
