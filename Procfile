web: scripts/entry.sh
celery_worker: cd trade_remedies_api && celery -A trade_remedies_api worker -l $CELERY_LOGLEVEL
celery_beat: cd trade_remedies_api && celery -A trade_remedies_api beat -l $CELERY_LOGLEVEL
