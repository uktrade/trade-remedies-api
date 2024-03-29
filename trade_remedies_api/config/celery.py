from celery import Celery
from celery.schedules import crontab

app = Celery("config")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "process-timegate-actions-hourly": {
        "task": "cases.tasks.process_timegate_actions",
        "schedule": crontab(minute=15),
    },
    "check-measure-expiry-daily": {
        "task": "cases.tasks.check_measure_expiry",
        "schedule": crontab(hour=0, minute=5),
    },
    "audit-notify-hourly": {
        "task": "audit.tasks.check_notify_send_status",
        "schedule": crontab(minute=30),
    },
    "geckoboard-update-hourly": {
        "task": "reports.tasks.update_geckoboard",
        "schedule": crontab(minute=0),
    },
    "index-documents-daily": {
        "task": "documents.tasks.index_documents",
        "schedule": crontab(hour=2, minute=0),
    },
}
