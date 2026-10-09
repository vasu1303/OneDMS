# Person 3: Mapping, Validation, and OEM Payload

## Assignment

You are the coding agent responsible for deterministic conversion into the OneDMS invoice structure, configurable validation, and a mock OEM output. Treat the LLM result as an untrusted proposal that must pass the same business checks as any other input.

## Current project context

- ORM definitions are in `backend/app/models/invoice.py`; the database design is `docs/architecture/OneDMS_Database_Design.md`.
- `mapping_configs` supports source-to-canonical and canonical-to-OEM JSON configuration. `validation_rules` stores JSON rule configuration.
- Those records are seeded, but there is no mapping engine, validation engine, or OEM adapter yet.
- The agreed POC scope is invoices only and the existing seven business tables. Do not add tables or Alembic/versioning as part of this assignment.

## Build

1. Define typed, independently testable mapping and validation services. Keep business logic free of FastAPI, SQLAlchemy sessions, and provider/network calls.
2. Implement source-to-canonical mapping from a supplied mapping configuration. Support the seeded mapping examples and document any deliberately unsupported transformation types. Missing paths must produce actionable issues, not silent nulls.
3. Normalize safely: dates to ISO dates, currency to uppercase ISO-like codes, and monetary/quantity values through `Decimal` rather than binary floating point. Do not invent missing invoice values.
4. Accept a PDF `canonical_candidate` from Person 2 and route it through the same canonical validation rules. Do not treat LLM output as pre-approved.
5. Implement the enabled validation rule types needed for the POC: required header/line fields, supported currency, positive quantity and valid prices, header/line total reconciliation with configured tolerance, duplicate invoice detection hook, and conditional chassis requirements only when the source/category configuration explicitly identifies a vehicle line.
6. Return structured results with rule code, severity, message, and affected field/line. A warning should not become an error; any confidence/review threshold must be agreed with Person 2 and Person 5.
7. Implement canonical-to-OEM mapping as a pure function driven by the supplied active configuration. Use a synthetic mock target payload only; do not send it to Daimler or claim a live integration.
8. Add tests for valid invoices, each major failure class, rounding tolerance, optional chassis for spare-parts lines, mapping path failures, and OEM output mapping.

## Shared canonical contract

Use database-compatible invoice fields:

- Header: `invoice_number`, `invoice_date`, `buyer_oem_id`, `currency`, `subtotal`, `tax_amount`, `total_amount`.
- Lines: `line_number`, optional `item_code`, `description`, `quantity`, `unit_price`, `discount_amount`, `taxable_amount`, optional `tax_rate`, `tax_amount`, `line_total`, optional `chassis_number`.
- Use decimal-compatible values internally. Person 5 is responsible for conversion to SQLAlchemy's numeric columns.

Validation/extraction metadata is not an OEM field. Agree with Person 5 on persisting safe review metadata under a reserved `_onedms` key in `canonical_payload`; do not create a new table or expose it in the OEM output.

## Ownership boundaries

- You own mapping and rule-evaluation functions plus the mock OEM payload mapper.
- Person 2 owns parsing and extraction; accept their typed input and return structured findings.
- Person 5 loads active configs/rules from the database, invokes your functions, persists the result, and exposes API responses.
- Person 4 displays issue codes/messages and invokes review APIs; coordinate a stable response shape.
- Do not own file intake, LLM transport, persistence, API routes, or frontend.

## Acceptance criteria

- Mapping and validation can run from in-memory config/data without a database or network.
- Every validation finding includes stable code, severity, message, and location where relevant.
- Valid input yields a canonical invoice; invalid or uncertain inputs are never silently marked valid.
- Spare-parts lines may omit `chassis_number`; vehicle-specific requirements apply only when the input/config provides a reliable vehicle classification.
- OEM output is generated from canonical values through configured mapping and excludes `_onedms` review metadata.
- Unit tests use synthetic data and never contact Neon, Object Storage, OpenRouter, or OEM services.

## Coordinate before coding

Agree on extraction-result types and candidate merging with Person 2. Agree on mapping-config loading, rule result shape, Decimal serialization, and review metadata persistence with Person 5. Share example API payloads with Person 4.
