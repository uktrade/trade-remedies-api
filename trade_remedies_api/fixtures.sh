#!/bin/bash
# Load all fixtures in one go

echo "Loading all fixture data"

python manage.py loaddata /app/security/fixtures/*.json
python manage.py loaddata /app/organisations/fixtures/*.json
python manage.py loaddata /app/cases/fixtures/*.json
python manage.py loaddata /app/core/fixtures/*.json

echo "Fixtures loaded"
