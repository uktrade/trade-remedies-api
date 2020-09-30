#!/bin/bash
# Load all fixtures in one go

echo "Loading all fixture data"

python ./manage.py loaddata ./trade_remedies_api/security/fixtures/*.json
python ./manage.py loaddata ./trade_remedies_api/organisations/fixtures/*.json
python ./manage.py loaddata ./trade_remedies_api/cases/fixtures/*.json
python ./manage.py loaddata ./trade_remedies_api/core/fixtures/*.json

echo "Fixtures loaded"
