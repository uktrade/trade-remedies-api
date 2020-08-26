#!/bin/bash
# Bootstrap a new environment, loading all fixtures, setting up security groups and initial
# data sets etc.

echo "Bootstrapping a new environment"

ARG1=${1-web}

if [ $ARG1 != 'test' ] && [ $ARG1 != 'code-quality' ]
then
    python ./trade_remedies_api/manage.py migrate
    python ./trade_remedies_api/manage.py resetsecurity
    python ./trade_remedies_api/manage.py adminuser
    python ./trade_remedies_api/manage.py s3credentials
    python ./trade_remedies_api/manage.py load_sysparams
    python ./trade_remedies_api/manage.py notify_env
    ./fixtures.sh
fi

if [ $ARG1 = 'web' ]
then
    python ./trade_remedies_api/manage.py runserver_plus 0.0.0.0:8000
elif [ $ARG1 = 'gunicorn' ]
then
    cd trade_remedies_api
    gunicorn trade_remedies_api.wsgi --bind 0.0.0.0:8000 --config ./trade_remedies_api/gunicorn.py
    exit 0
elif [ $ARG1 = 'cli' ]
then
    cd trade_remedies_api && /bin/bash
    exit 0
elif [ $ARG1 = 'celery-worker' ]
then
    cd trade_remedies_api && celery -A trade_remedies_api worker -l $CELERY_LOGLEVEL
    exit 0
elif [ $ARG1 = 'celery-beat' ]
then
    cd trade_remedies_api && celery -A trade_remedies_api beat -l $CELERY_LOGLEVEL
    exit 0
elif [ $ARG1 = 'test' ]
then
    cd trade_remedies_api && coverage run manage.py test && coverage xml && coverage report
    exit 0
elif [ $ARG1 = 'code-quality' ]
then
    black trade_remedies_api --check # || flake8
fi
