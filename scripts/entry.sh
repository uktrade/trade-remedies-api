#!/bin/bash -e

cd ${HOME}/trade_remedies_api
python ./manage.py migrate 
python ./manage.py load_sysparams
python ./manage.py notify_env
python ./manage.py collectstatic --noinput 

gunicorn trade_remedies_api.wsgi --bind 0.0.0.0:$API_PORT --capture-output --config trade_remedies_api/gunicorn.py
