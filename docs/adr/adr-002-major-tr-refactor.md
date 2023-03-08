# ADR-002: Major TR refactor

## Status

[![Generic badge](https://badgen.net/badge/ADR/approved/green/)](https://github.com/uktrade/trade-remedies-api/adr/README.md)

## Context

The TRS was implemented by a small, delivery focussed team who needed to
understand a complicated domain as well as deliver a solution within very
tight timescales. There were numerous unknown and unforeseeable elements to
the project and as such the service has accrued significant technical debt.
Subsequently, the service has low test coverage, is difficult to maintain,
adding new features is onerous and there are usability and performance issues.

The service's code base was assessed and a report published on the findings.
To improve the service's maintainability, extensibility and performance it
either needs to be re-written, or a significant refactor must take place.

## Decision

- Perform a large-scale refactor of the Trade Remedies Service:
  - Use canonical approaches in the API implementation.
  - Simplify the API implementation.
  - Rework the underlying data model to support latest user requirements.

## Consequences

- There will be less duplication in the code base.
- Test driven development will be more possible when fixing issues, due to
  better test coverage.
- It will take less time to identify and fix bugs.
- It will take less time to add much needed new features.
- The system will provide a better user experience.
- The system will be more performant, will scale better to cope with a
  higher number of cases and more users.
- The system will be more robust.
- Regressions will be less likely due to more complete test
  coverage.
