#!/usr/bin/env bash

set -e

export CASE_WORKER_ENVIRONMENT_KEY="example"
export DJANGO_SECRET_KEY="example"
export PUBLIC_ENVIRONMENT_KEY="example"
export DATABASE_URL=psql://postgres:postgres@banana:5432/trade_remedies

python ./trade_remedies_api/manage.py collectstatic --noinput
