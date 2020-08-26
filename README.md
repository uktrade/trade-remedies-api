# trade-remedies-api
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-9-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->
Back end API to support the Trade Remedies service.

## Code Style

Live Services Team use [Black](https://black.readthedocs.io/en/stable/index.html) for python code formatting and
[flake8](https://flake8.pycqa.org/en/latest/) for code analysis. 

#### Useful commands:

```
make docker_code_quality
```
runs black and flake8 in a container the same as circle ci

#### Running locally without docker

```shell script
    # ensure you have a virtualenv
    python3 -m venv env
    pip install -r requirements-dev.txt
  

    black trade_remedies_api --check

    flake8

```

Please format your django templates using PyCharm's built in formatter. (Unless you can find a suitable alternative)

### Running via Docker

#### Development

The stack can be brought up using docker-compose, backed with a Postgresql 10 database and Redis instance.

Firstly, you should copy example.env to local.env and add the necessary
environment variables for a local development environment.  local.env is in
.gitignore and should not be committed to the repo.

```
make docker-cli
```

This will drop you into a terminal session within the container where you can
run the usual commands eg

```
# Run the development server
python manage.py runserver_plus 0.0.0.0:8000
# Use the python / django shell
python manage.py shell_plus
# Run the django test suite
python manage.py test
```

Any changes made to source files on your local computer will be reflected in
the container.

The Postgresql database is available from your host machine on port 5432.
The Redis database is available from your host machine on port 6379.

#### Connect to a running container

You can start additional terminal sessions on an already running container as
follows:

```
make docker-cli-connect
```

#### Run celery tasks in a separate worker

By default the celery tasks are configured to run *eagerly* ie in the same
process as django within the development container.
To test tasks in a separate celery worker you should change
CELERY_TASK_ALWAYS_EAGER in your *local.env* file and stop your *cli* container.

Then restart a new *cli* and *celery-worker* container.

```
make docker-cli
make docker-celery-worker
```

If you want to test periodic tasks with full celery integration you can also
run celery beat.

```
make docker-celery-beat
```

### Full Dockerised environment

The repository at https://github.com/uktrade/trade-remedies-docker contains
a fully dockerised environment containerised and integrated together.
To use it, clone the repository at the same level of the api, caseworker and public
repositories and run `docker-compose-up` to bring it up.
More information is within the repository.

#### Unit tests

The unit tests can also be executed in an isolated docker environment.

```
make docker-test
```

### Running standalone

It's also possible to run the environment as a standalone local app, using virtualenv.
This assumes you have virtualenvwrapper installed, and a virtual env is created (either
via `mkvirtualenv trade-remedies-api` for example).
Use Python 3.6+ as your interpretor.
Make sure to install PostgreSql and Redis locally to use the service.

```
workon trade-remedies-api
./manage.py runserver
```



## Deployment

Trade Remedies API configuration is performed via the following environment variables:


| Variable name | Required | Description |
| ------------- | ------------- | ------------- |
| `ALLOWED_HOSTS` | Yes | Comma-separated list of hostnames at which the app is accessible |
| `DEBUG`  | Yes | Whether Django's debug mode should be enabled. |
| `DJANGO_SECRET_KEY`  | Yes | |
| `DJANGO_SETTINGS_MODULE`  | Yes | |
| `DB_HOST` | Yes | The postgres database host |
| `DB_PORT` | Yes | The postgres database port |
| `DB_NAME` | Yes | The postgres databse name |
| `DB_USER` | Yes | The postgres database user |
| `DB_PASSWORD` | Yes | The postgres database password |
| `MASTER_ADMIN_EMAIL` | Yes | Admin super user email (login) |
| `MASTER_ADMIN_PASSWORD` | Yes | Admin super use password
| `SENTRY_DSN` | Yes | URL For Sentry logging |
| `HEALTH_CHECK_USER_TOKEN` | Yes | Auth token to use for the health check (trusted) user |
| `HEALTH_CHECK_USER_EMAIL` | No | default: `_healthcheckuser_@gov.uk` |
| `S3_STORAGE_KEY` | Yes | AWS S3 key |
| `S3_STORAGE_SECRET` | Yes | AWS S3 secret |
| `S3_BUCKET_NAME` | No | Defaults to `trade-remedies-file-storage-dev` |
| `AV_SERVICE_URL` | Yes | Url for the Antivirus service |
| `AV_SERVICE_USERNAME` | Yes | Username for the Antivirus service |
| `AV_SERVICE_PASSWORD` | Yes | Password for the Antivirus service |
| `GOV_NOTIFY_API_KEY`  | Yes | API Key for GOV Notify |
| `GOV_NOTIFY_SERVICE_ID` | Yes | Service ID for GOV Notify |
| `GOV_NOTIFY_SERVICE_API_KEY` | Yes | Service API Key for GOV Notify |
| `PUBLIC_ROOT_URL` | Yes | Root URL for the Customer facing app |
| `CASE_WORKER_ENVIRONMENT_KEY` | Yes | Unique identifier of the Case Worker environment used for API access restriction (Default value set) |
| `PUBLIC_ENVIRONMENT_KEY` | Yes | Unique identifier of the Customer environment used  |for API access restriction (Default value set) |
| `VCAP_SERVICES` | Yes | [CloudFoundry-compatible ](https://docs.run.pivotal.io/devguide/deploy-apps/environment-variable.html#VCAP-SERVICES)/[GDS PaaS-compatible](https://docs.cloud.service.gov.uk/deploying_apps.html#system-provided-environment-variables) configuration. The connection string at `redis[0].credentials.uri` is used to connect to Redis, which must include the password if required. It should _not_ end a forward slash. The connection string at `elasticsearch[0].credentials.uri` is used for Elasticsearch. When not present the dedicated HOST/PORT settings below will be used. |
| `REDIS_DATABASE_NUMBER` | Yes | The database number in the Redis instance connected to by the details in `VCAP_SERVICES`. |
| `DJANGO_ADMIN` | No | Set to True to turn on Django's admin site. Not for production environment! |
| `ELASTIC_HOST` | No | Optional host for Elasticsearch host, for when VCAP_SERVICES does not provide credentials (local development). |
| `ELASTIC_PORT` | No | Optional host for Elasticsearch port, for when VCAP_SERVICES does not provide credentials (local development). |

### Scripts

After the system is deployed for the first, the `bootstrap.sh` script will facilitate
running the migrations, and setting up the data including running `fixtures.sh` which is setting up all fixtures. On an ongoing basis, only `fixtures.sh` is needed whenever fixtures are updated.

--- 


## Contributors ✨

Thanks goes to these wonderful people who contributed to this repo before it was open-sourced ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tr>
    <td align="center"><a href="http://www.harelmalka.com/"><img src="https://avatars3.githubusercontent.com/u/985978?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Harel Malka</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/commits?author=harel" title="Code">💻</a> <a href="https://github.com/uktrade/trade-remedies-api/commits?author=harel" title="Documentation">📖</a> <a href="https://github.com/uktrade/trade-remedies-api/pulls?q=is%3Apr+reviewed-by%3Aharel" title="Reviewed Pull Requests">👀</a></td>
    <td align="center"><a href="https://github.com/bobmeredith"><img src="https://avatars2.githubusercontent.com/u/11422209?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Robert Meredith</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/commits?author=bobmeredith" title="Code">💻</a> <a href="#design-bobmeredith" title="Design">🎨</a></td>
    <td align="center"><a href="https://github.com/Luisella21"><img src="https://avatars1.githubusercontent.com/u/36708790?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Luisella Strona</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/pulls?q=is%3Apr+reviewed-by%3ALuisella21" title="Reviewed Pull Requests">👀</a></td>
    <td align="center"><a href="https://github.com/markhigham"><img src="https://avatars1.githubusercontent.com/u/2064710?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Mark Higham</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/commits?author=markhigham" title="Code">💻</a></td>
    <td align="center"><a href="https://github.com/nao360"><img src="https://avatars3.githubusercontent.com/u/6898065?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Nao Yoshino</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/commits?author=nao360" title="Code">💻</a></td>
    <td align="center"><a href="https://github.com/ulcooney"><img src="https://avatars0.githubusercontent.com/u/1695475?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Paul Cooney</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/commits?author=ulcooney" title="Code">💻</a></td>
    <td align="center"><a href="http://charemza.name/"><img src="https://avatars1.githubusercontent.com/u/13877?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Michal Charemza</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/commits?author=michalc" title="Code">💻</a> <a href="https://github.com/uktrade/trade-remedies-api/pulls?q=is%3Apr+reviewed-by%3Amichalc" title="Reviewed Pull Requests">👀</a></td>
  </tr>
  <tr>
    <td align="center"><a href="https://github.com/krishnawhite"><img src="https://avatars1.githubusercontent.com/u/5566533?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Krishna White</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/commits?author=krishnawhite" title="Code">💻</a></td>
    <td align="center"><a href="http://blog.clueful.com.au/"><img src="https://avatars0.githubusercontent.com/u/309976?v=4?s=100" width="100px;" alt=""/><br /><sub><b>Brendan Quinn</b></sub></a><br /><a href="https://github.com/uktrade/trade-remedies-api/commits?author=bquinn" title="Code">💻</a></td>
  </tr>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!