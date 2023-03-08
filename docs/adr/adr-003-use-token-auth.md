# ADR-003: Use DRF Token Authentication

## Status

[![Generic badge](https://badgen.net/badge/ADR/approved/green/)](https://github.com/uktrade/trade-remedies-api/adr/README.md)

## Context

As the Trade Remedies API undergoes a [major refactor (ADR-002)](adr-002-major-tr-refactor.md)
there is a requirement to rework the Caseworker and Public portal
authentication with the API layer.

The API uses the Django Rest Framework (DRF) in its current implementation
and there are no motivations to change this. However, the DRF usage is
overcomplicated, suboptimally and non-canonically implemented. A simpler
approach to Portal-to-API authentication needs to be implemented. Central to
this is using a standard DRF API approach to API authentication. Choices are
as follows:

- Basic
  - Basic authentication is generally only appropriate for testing.
- Token
  - Appropriate for client-server setups.
- Session
  - Session authentication is appropriate for AJAX clients that are running
    in the same session context as your website
- Remote User
  -  Allows you to delegate authentication to your web server (e.g. NGINX).
- Custom
  - Used to provide a specific authentication model if the system has
    particular requirements.

Given the options, `Token` should be considered the most appropriate.
`Session` is recommended for "RIA" type apps running in the same context as
the API itself. `Remote User` does not fit in with the PaaS deployment model
uses in PaaS at the DIT. There are no special requirements for Portal-to-API
authentication so `Custom` is overkill.

## Decision

- Use DRF Token Authentication for Portal-to-API authentication.

## Consequences

- The Portal-to-API authentication implementation will be simple.
- The Portal-to-API authentication implementation will be easier to maintain.
- The Portal-to-API authentication implementation will be less likely to
  incorporate unforeseen security issues.
- Token management will be compatible with the existing deployment pattern.
