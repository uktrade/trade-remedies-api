#!/bin/bash -e

pwd 
ls -al
cd ./trade_remedies_api
python ./manage.py migrate
python ./manage.py load_sysparams
python ./manage.py notify_env
python ./manage.py collectstatic --noinput

gunicorn config.wsgi --bind 0.0.0.0:$API_PORT --capture-output --config config/gunicorn.py
