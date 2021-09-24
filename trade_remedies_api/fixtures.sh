#!/bin/bash
# Load all fixtures in one go

echo "Loading all fixture data"

python manage.py loaddata security/fixtures/*.json
python manage.py loaddata organisations/fixtures/*.json
python manage.py loaddata cases/fixtures/*.json
python manage.py loaddata core/fixtures/*.json

echo "Fixtures loaded"
