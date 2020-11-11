#!/bin/bash -e

[[ "$INSTANCE_INDEX" == 0 ]] && cd trade_remedies_api && python ./manage.py migrate && python ./manage.py resetsecurity && python ./manage.py adminuser && python ./manage.py loaddata core/fixtures/*.json && python ./manage.py loaddata security/fixtures/*.json && python ./manage.py loaddata organisations/fixtures/*.json && python ./manage.py loaddata cases/fixtures/*.json && python ./manage.py load_sysparams && python ./manage.py s3credentials && python ./manage.py notify_env && python ./manage.py collectstatic --noinput 

cd trade_remedies-api
gunicorn trade_remedies_api.wsgi --bind 0.0.0.0:$API_PORT --config trade_remedies_api/gunicorn.py

