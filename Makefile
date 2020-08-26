SHELL := /bin/bash
APPLICATION_NAME="Trade Remedies API"
APPLICATION_VERSION=1.0
VENV_PATH=./env/bin

# Colour coding for output
COLOUR_NONE=\033[0m
COLOUR_GREEN=\033[32;01m
COLOUR_YELLOW=\033[33;01m


.PHONY: help test
help:
		@echo -e "$(COLOUR_GREEN)|--- $(APPLICATION_NAME) [$(APPLICATION_VERSION)] ---|$(COLOUR_NONE)"
		@echo -e "$(COLOUR_YELLOW)make test$(COLOUR_NONE) : Run the test suite"
		@echo -e "$(COLOUR_YELLOW)make docker-test$(COLOUR_NONE) : Run the test suite in a dockerized environment"
		@echo -e "$(COLOUR_YELLOW)make docker-cli$(COLOUR_NONE) : Start a terminal session in a dockerized environment for development"
		@echo -e "$(COLOUR_YELLOW)make docker-cli-connect$(COLOUR_NONE) : Start a new terminal session in a running cli container "
		@echo -e "$(COLOUR_YELLOW)make docker-celery-worker$(COLOUR_NONE) : Start a separate celery worker in a dockerized environment for development"
		@echo -e "$(COLOUR_YELLOW)make build-docker-cli$(COLOUR_NONE) : Rebuild the dockerized environment for development"
		@echo -e "$(COLOUR_YELLOW)make flake8$(COLOUR_NONE) : Run flake8 checks"
		@echo -e "$(COLOUR_YELLOW)make black$(COLOUR_NONE) : Run black checks"


test:
		$(VENV_PATH)/python ./trade_remedies_api/manage.py test ./trade_remedies_api/security;
		$(VENV_PATH)/python ./trade_remedies_api/manage.py test ./trade_remedies_api/cases;
		$(VENV_PATH)/python ./trade_remedies_api/manage.py test ./trade_remedies_api/core;

bootstrap:
		$(VENV_PATH)/python ./trade_remedies_api/manage.py migrate;
		$(VENV_PATH)/python ./trade_remedies_api/manage.py resetsecurity;
		$(VENV_PATH)/python ./trade_remedies_api/manage.py adminuser;
		$(VENV_PATH)/python ./trade_remedies_api/manage.py loaddata ./trade_remedies_api/security/fixtures/*.json;
		$(VENV_PATH)/python ./trade_remedies_api/manage.py loaddata ./trade_remedies_api/cases/fixtures/*.json;
		$(VENV_PATH)/python ./trade_remedies_api/manage.py loaddata ./trade_remedies_api/core/fixtures/*.json;
		$(VENV_PATH)/python ./trade_remedies_api/manage.py s3credentials;

docker-test:
		docker-compose -f docker-compose-test.yml -p trade-remedies-api-test rm --force
		docker-compose -f docker-compose-test.yml -p trade-remedies-api-test run test-trade-remedies-api
		docker-compose -f docker-compose-test.yml -p trade-remedies-api-test stop
		docker-compose -f docker-compose-test.yml -p trade-remedies-api-test rm --force


black:
		docker run -it --rm -v api-requirements:/usr/local -v "$(CURDIR):/app" python sh -c "cd /app && pip install -r requirements-dev.txt && black trade_remedies_api --check"

flake8:
		docker run -it --rm -v api-requirements:/usr/local -v "$(CURDIR):/app" python sh -c "cd /app && pip install -r requirements-dev.txt && flake8 --count"

docker-cli:
		docker-compose -f docker-compose.yml run --service-ports --rm --name trade-remedies-api-cli cli
		docker-compose -f docker-compose.yml stop

docker-celery-worker:
		docker-compose -f docker-compose.yml run --service-ports --rm --name trade-remedies-api-celery-worker worker /opt/traderemedies/api/bootstrap.sh celery-worker
		docker-compose -f docker-compose.yml stop worker

docker-celery-beat:
		docker-compose -f docker-compose.yml run --service-ports --rm --name trade-remedies-api-celery-beat beat /opt/traderemedies/api/bootstrap.sh celery-beat
		docker-compose -f docker-compose.yml stop beat

docker-cli-connect:
		docker exec -i -t trade-remedies-api-cli /bin/bash

build-docker-cli:
		docker-compose -f docker-compose.yml build cli

build-docker-celery-worker:
		docker-compose -f docker-compose.yml build worker

build-docker-celery-beat:
		docker-compose -f docker-compose.yml build beat

