#!/bin/bash
# Load all fixtures in one go

echo "Loading all fixture data"

python ./trade_remedies_api/manage.py loaddata ./trade_remedies_api/security/fixtures/*.json
python ./trade_remedies_api/manage.py loaddata ./trade_remedies_api/organisations/fixtures/*.json
python ./trade_remedies_api/manage.py loaddata ./trade_remedies_api/cases/fixtures/*.json
python ./trade_remedies_api/manage.py loaddata ./trade_remedies_api/core/fixtures/*.json

echo "Fixtures loaded"
