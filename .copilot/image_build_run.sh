#!/usr/bin/env bash

set -e

export CASE_WORKER_ENVIRONMENT_KEY="example"
export DJANGO_SECRET_KEY="example"
export PUBLIC_ENVIRONMENT_KEY="example"

python ./trade_remedies_api/manage.py collectstatic --noinput