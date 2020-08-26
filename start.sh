#!/bin/bash -xe
python /opt/traderemedies/api/trade_remedies_api/manage.py migrate --noinput
python /opt/traderemedies/api/trade_remedies_api/manage.py loaddata /opt/traderemedies/api/trade_remedies_api/cases/fixtures/*
python /opt/traderemedies/api/trade_remedies_api/manage.py loaddata /opt/traderemedies/api/trade_remedies_api/security/fixtures/*
python /opt/traderemedies/api/trade_remedies_api/manage.py loaddata /opt/traderemedies/api/trade_remedies_api/core/fixtures/*
python /opt/traderemedies/api/trade_remedies_api/manage.py load_sysparams
python /opt/traderemedies/api/trade_remedies_api/manage.py adminuser
python /opt/traderemedies/api/trade_remedies_api/manage.py runserver_plus 0.0.0.0:8000
