# ADR-004: Use Django RESTQL Package

## Status

[![Generic badge](https://badgen.net/badge/ADR/approved/green/)](https://github.com/uktrade/trade-remedies-api/adr/README.md)

[django-restql]: (https://pypi.org/project/django-restql/)

## Context

There is a motivation to drastically simplify the TR API service to improve
maintainability. Using _all_ the Django Rest Framework capabilities including
Model Serializers, Model Views and Viewsets will help.

We would like to support all existing and perceived requirements, while
avoiding the common REST API issue of under or over fetching.

This could result in a proliferation of serializers and views to provide all 
the various shapes of data to support various user features efficiently.

A possible solution to under/over fetching is to employ a [GraphQL](https://graphql.org/)
based API, e.g. using [Django Graphene](https://pypi.org/project/graphene-django/).
GraphQL might be a good choice if the API was intended to be long-lived,
or had disparate clients where the bulk of use-cases were hitherto unknown.

However, we know that the API is a medium term, tactical solution. That is,
once the large scale refactor is complete we would like to collapse down TR
into a single service, combining the API with the Portal services. Furthermore,
GraphQL can make some simple tasks more complex and there is a barrier to
entry for the portal developer who is not familiar with the GraphQL syntax.

A solution identified is the [Django RESTQL][django-restql] python package.
This is a python library which will enable us to adapt our standard
Django REST Framework based API into a GraphQL-like API. In concert with DRF,
Django RESTQL enables a REST client to utilise a `query` parameter to refine
data requested, and employs CRUD logic levers in the request body to refine
POST, PUT and PATCH requests. Reasonable
[documentation exists](https://yezyilomo.github.io/django-restql/),
the project is compact, contains tests (coverage not known) and is recently
maintained.
 
## Decision

- Use the [Django RESTQL][django-restql] package.

## Consequences

- The API footprint will be smaller, therefore easier to maintain.
- Client operations will be simpler to implement.
- Client requirements can be fulfilled flexibly and efficiently.
- Lower cognitive load on developer with fairly easy to understand tool.
