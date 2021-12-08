web: scripts/entry.sh
celery_worker: cd trade_remedies_api && celery -A config worker -l $CELERY_LOGLEVEL
celery_beat: cd trade_remedies_api && celery -A config beat -l $CELERY_LOGLEVEL
