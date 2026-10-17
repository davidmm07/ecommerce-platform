# E-commerce Platform

A full stack e-commerce application built as if it were a real corporate project: a **FastAPI**
backend designed with **Clean Architecture**, a **PostgreSQL** database, and a **React +
TypeScript + TanStack** frontend, packaged as a **Docker Compose** monorepo.

It covers product CRUD, CSV import, full-text product search, and a purchase flow with a simulated
payment provider. Stock reservation is concurrency safe, payments are idempotent, and a failed
payment releases the stock it reserved.

---

## Contents

1. [Highlights](#highlights)
2. [Quick start with Docker](#quick-start-with-docker)
3. [Local development](#local-development)
4. [The sample CSV](#the-sample-csv)
5. [Approach](#approach)
6. [Architecture: Clean vs Layered](#architecture-clean-vs-layered)
7. [Database: PostgreSQL vs MongoDB](#database-postgresql-vs-mongodb)
8. [Design patterns](#design-patterns)
9. [SOLID in practice](#solid-in-practice)
10. [API design](#api-design)
11. [Data validation](#data-validation)
12. [Error handling](#error-handling)
13. [Purchase flow](#purchase-flow)
14. [Product search](#product-search)
15. [CSV import rules](#csv-import-rules)
16. [Frontend](#frontend)
17. [Testing and quality gates](#testing-and-quality-gates)
18. [Security notes](#security-notes)
19. [Configuration](#configuration)
20. [Alternatives considered](#alternatives-considered)
21. [Known limitations and next steps](#known-limitations-and-next-steps)

## Highlights

| Area | What is implemented |
|------|---------------------|
| Product CRUD | Create, read, partial update and soft delete, with optimistic concurrency (`ETag` / `If-Match`) |
| CSV import | Upload or CLI, row level report, dry run, upsert by SKU, duplicate detection, one transaction |
| Search | PostgreSQL full-text search plus trigram fuzzy matching, filters, sorting and pagination |
| Purchase | Cart, server side quote, weight based shipping, simulated card payments, idempotent checkout |
| Consistency | Row locks prevent overselling, a failed payment releases its stock (compensation) |
| API | Versioned REST, RFC 9457 Problem Details, OpenAPI docs, request ids, size limits |
| Frontend | TanStack Router, Query, Table, Form and Store, Zod validation, Tailwind CSS |
| Quality | 192 backend tests (97% coverage) incl. real PostgreSQL via Testcontainers, 30 frontend tests, `mypy --strict`, architecture contracts, CI |
| Delivery | Monorepo, multi stage non-root images, Compose stack with migrations, health checks and a seed job |

## Quick start with Docker

Requirements: Docker with Compose v2, `make` and `python3` (only used to generate the `.env`).

```bash
make up
```

```bash
make seed
```

`make up` creates a git ignored `.env` with a random database password the first time, builds the
images and starts PostgreSQL, the migration job, the API and the web app. `make seed` imports the
sample CSV through the same use case the UI uses.

| URL | What |
|-----|------|
| http://localhost:8080 | Web app (shop, cart, checkout, orders, product admin, CSV import) |
| http://localhost:8000/docs | Interactive OpenAPI documentation |
| http://localhost:8000/health/ready | Readiness probe (checks the database) |

Without `make`, create the `.env` yourself and use Compose directly:

```bash
printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 16)" > .env
```

```bash
docker compose up --build -d
```

```bash
docker compose --profile seed run --rm seed
```

`make down` stops the stack and keeps the data, `make clean` also deletes the database volume.

## Local development

Requirements: Python 3.13 with [uv](https://docs.astral.sh/uv/), Node.js 22.12 or newer, Docker
(for PostgreSQL and for the integration tests).

```bash
make install
```

```bash
make dev-db
```

```bash
make dev-api
```

```bash
make dev-web
```

Run `make dev-api` and `make dev-web` in two terminals. `dev-api` applies the migrations and starts
Uvicorn with reload on port 8000. `dev-web` starts Vite on http://localhost:5173 and proxies `/api`
to the backend, so no CORS setup is needed.

Quality checks, the same ones CI runs:

```bash
make check
```

The backend integration and API tests start a disposable PostgreSQL container with Testcontainers.
To reuse an existing database instead, export `TEST_DATABASE_URL`, for example
`postgresql+asyncpg://user:password@localhost:5432/ecommerce_test`. The tests reset its schema.

## The sample CSV

The provided example file, `LoanPro Code Challenge E-Commerce - LoanPro Code Challenge
E-Commerce.csv`, was **downloaded on October 17, 2026** (2026-10-17). It is stored unchanged in
[`data/products-sample.csv`](data/products-sample.csv) (SHA-256
`6fc46b84badb1ac37b8b19a2d0741aa7728d6c93a9fe949b19f676892dc8fd24`).

It has 97 data rows with deliberate data quality problems. This is how each one is handled.
Line numbers include the header, so they match what a spreadsheet shows.

| Line | SKU | Problem in the data | Decision | Result |
|------|-----|---------------------|----------|--------|
| 4 | WM-042 | Price `$29.99` | A leading `$` is unambiguous for a USD catalog, so it is stripped and reported | Created, with a note |
| 7 | YM-015 | Price `free` | Never guess a price | Failed |
| 16 | DL-007 | Stock `-5` | Stock cannot be negative | Failed |
| 20 | XS-001 | Name `<script>alert('xss')</script>` | Text fields are plain text, markup is rejected (React also escapes output) | Failed |
| 25 | HD-099 | Empty name | Name is required | Failed |
| 29 | SQL-001 | Name `Robert'); DROP TABLE products;--` | A legitimate string: stored verbatim, parameterized SQL keeps it harmless | Created |
| 31 | WB-033 | Em dash and trademark sign | UTF-8 is preserved and normalized to NFC | Created |
| 41 | WS-001 | Name made only of spaces | Whitespace is trimmed, so it is empty | Failed |
| 47 | MB-001 | Price `0.00` | Sellable products must cost more than 0, promotions belong in discounts | Failed |
| 50 | GK-088 | Missing weight | Weight drives shipping cost, it is required | Failed |
| 51 | VC-001 | Stock `0` | Valid, shown as out of stock | Created |
| 52 | GC-025 | Missing category | Category is required | Failed |
| 53, 59 | CI-001, QI-001 | Comma and escaped quotes in names | RFC 4180 parsing | Created |
| 55 | RS-050 | Same name as RS-001, different SKU | Names are not unique, the SKU is the identity | Created |
| 2 and 36 | RS-001 | Same SKU twice, line 36 says "Updated" | File order is chronological, the last row wins, line 2 is reported as superseded | Line 36 created |
| 11, 56, 89 | BS-021 | Same SKU three times, line 89 repeats line 11 | Last row wins, every superseded row is reported | Line 89 created |
| 62, 63 | - | Blank rows | Ignored and reported | Skipped |

Summary: **84 created, 5 skipped, 8 failed**. Importing the same file again reports 84 unchanged
rows, so the import is idempotent.

## Approach

1. **Model the business first.** Money, SKU, category, product, order and payment card are domain
   objects that validate themselves. The CSV quirks above turned into explicit, tested rules
   instead of ad hoc parsing code.
2. **Use cases as the API of the backend.** Every feature is an application use case such as
   `CreateProduct`, `ImportProducts`, `QuoteCart` or `PlaceOrder`. FastAPI and the CLI are thin
   adapters around them.
3. **Let the database do what it is good at.** Constraints back up the domain rules, row locks make
   stock reservation safe, and full-text and trigram indexes power search.
4. **Treat failure as a feature.** Every error has a stable code and HTTP status. Payments can be
   declined, time out or be retried, and the system stays consistent in each case.
5. **Make it operable.** The stack ships with migrations as a separate job, health probes, JSON logs
   with request ids, non-root containers, and a CI pipeline that also boots the Compose stack.

## Architecture: Clean vs Layered

**Decision: Clean Architecture (Ports and Adapters), organized by layer with bounded contexts
inside each layer.**

| Question | Layered (n-tier) | Clean Architecture (chosen) |
|----------|------------------|-----------------------------|
| Where do dependencies point? | Downwards, business code imports the ORM | Inwards, the ORM depends on the domain |
| Can the checkout rules be tested without a database? | Only with heavy mocking | Yes, with in-memory adapters in milliseconds |
| Several delivery mechanisms (REST API, CLI seed job) | Logic tends to leak into each one | Both call the same use cases |
| Replacing the payment provider, CSV with XLSX, or PostgreSQL | Touches services | A new adapter plus one line in the composition root |
| Ceremony | Lower | Higher: ports, mappers and DTOs, which is the trade-off |

Why it fits this project:

- **The rules are the valuable part.** Stock reservation, price snapshots, the order state machine,
  idempotency and the import policy change for business reasons and must not depend on FastAPI or
  SQLAlchemy versions.
- **There is real I/O variability.** A payment gateway, a file format and a database are exactly the
  details that ports isolate. The simulated gateway can be swapped for Stripe or Adyen without
  touching the checkout use case.
- **Testability drove the design.** 133 of the backend tests run without a database in under a
  second, while integration tests prove the adapters against a real PostgreSQL.

Layered architecture would be a reasonable choice for a CRUD-only service. The cost of Clean
Architecture (more files, mapping between ORM records and entities) is paid back here because the
purchase flow and the import have non-trivial rules.

```mermaid
flowchart LR
    subgraph Presentation
        API["FastAPI routers, schemas, problem details"]
        CLI["CLI: import-products"]
    end
    subgraph Composition
        C["Container (composition root)"]
    end
    subgraph Application
        UC["Use cases: CreateProduct, UpdateProduct, ArchiveProduct, SearchProducts, ImportProducts, QuoteCart, PlaceOrder, GetOrder, ListOrders"]
        P["Ports: UnitOfWork, repositories, read models, PaymentGateway, Clock, ProductTableReader"]
    end
    subgraph Domain
        D["Catalog: Product, Sku, Category<br/>Ordering: Order, pricing, shipping<br/>Payments: PaymentCard<br/>Shared: Money"]
    end
    subgraph Infrastructure
        DB["SQLAlchemy async + PostgreSQL"]
        PAY["Simulated payment gateway + resilience decorator"]
        CSV["CSV reader"]
    end
    API --> C
    CLI --> C
    C --> UC
    C --> DB
    C --> PAY
    C --> CSV
    UC --> P
    UC --> D
    DB -. implements .-> P
    PAY -. implements .-> P
    CSV -. implements .-> P
```

The dependency rule is **enforced in CI** with `import-linter` contracts in
[`backend/pyproject.toml`](backend/pyproject.toml):

- layers only import inwards: presentation and CLI, then container, infrastructure, application, domain;
- the domain and application layers cannot import FastAPI, Pydantic, SQLAlchemy or asyncpg;
- the catalog, ordering and payments domain contexts are independent of each other.

### Project structure

```text
.
|-- backend/
|   |-- src/ecommerce/
|   |   |-- domain/            entities, value objects, domain errors (no frameworks)
|   |   |   |-- catalog/       Product, ProductDetails, Sku, Category
|   |   |   |-- ordering/      Order, OrderLine, Customer, ShippingAddress, pricing and shipping
|   |   |   `-- payments/      PaymentCard, Luhn check, brand detection
|   |   |-- application/       use cases, commands, ports, pagination, application errors
|   |   |   |-- catalog/       CRUD and search use cases, search criteria
|   |   |   |-- imports/       ImportProducts, row parser, import report
|   |   |   |-- ordering/      QuoteCart, PlaceOrder, GetOrder, ListOrders
|   |   |   `-- ports/         UnitOfWork, repositories, read models, PaymentGateway, Clock
|   |   |-- infrastructure/    adapters: persistence, payments, files, config, logging
|   |   |-- presentation/api/  FastAPI app, routers, schemas, middleware, problem details
|   |   |-- container.py       composition root (dependency injection)
|   |   `-- cli.py             operational commands (seed import)
|   |-- migrations/            Alembic migrations
|   `-- tests/                 unit, integration (PostgreSQL) and API tests
|-- frontend/
|   |-- src/app/               router, layout, query client
|   |-- src/features/          catalog, cart, checkout, orders, imports (feature folders)
|   |-- src/shared/            HTTP client, UI components, formatting and form helpers
|   `-- nginx/                 production web server config
|-- data/products-sample.csv   the provided example file
|-- docker-compose.yml         db, migrate, api, web and seed services
|-- Makefile                   one entry point for every workflow
`-- .github/workflows/ci.yml   lint, types, tests, build, and a Compose smoke test
```

A **monorepo** keeps the API contract, the UI that consumes it and the deployment definition in one
change set: a pull request that changes an endpoint also changes the frontend and is verified by
one CI run. Each app keeps its own toolchain (uv for Python, npm for Node) and Dockerfile, so they
can be extracted into separate repositories later if teams split.

## Database: PostgreSQL vs MongoDB

**Decision: PostgreSQL 17.**

| Criterion | PostgreSQL (chosen) | MongoDB |
|-----------|---------------------|---------|
| Shape of the data | Uniform product schema, orders with lines that reference products: relational | Flexible documents, best when product attributes vary a lot |
| Checkout consistency | ACID transactions and `SELECT ... FOR UPDATE` across products and orders in one statement | Multi-document transactions need a replica set and are more limited |
| Money | Exact `NUMERIC(12,2)` | `Decimal128`, workable but less common in drivers and tooling |
| Integrity at rest | `CHECK` constraints (price > 0, stock >= 0, known category), unique and foreign keys | Schema validation is optional and weaker |
| Search | Built-in full-text search (`tsvector`, GIN) and `pg_trgm` fuzzy matching | Text indexes (no fuzzy matching) or Atlas Search, which is a managed service |
| Operations | Alembic migrations, mature backups and tooling | Schemaless evolution, but migrations still exist in practice |

MongoDB would win for a catalog with highly heterogeneous attributes per category. If that need
appears, PostgreSQL `JSONB` columns cover it without giving up transactions.

## Design patterns

| Pattern | Where | Why |
|---------|-------|-----|
| Repository | `ProductRepository`, `OrderRepository` ports, SQLAlchemy adapters and in-memory test fakes | Use cases talk about aggregates, not SQL |
| Unit of Work | `UnitOfWork` port, `SqlAlchemyUnitOfWork` | One transaction per business operation, explicit commit, automatic rollback |
| Template Method | `UnitOfWork.__aenter__`/`__aexit__` call `_begin`, `rollback`, `_end` hooks | The transaction lifecycle is written once, adapters fill in the steps |
| Data Mapper | `ProductMapper`, `OrderMapper` | Domain entities stay free of ORM state, the ORM records stay free of rules |
| Strategy | `ShippingPolicy` (`WeightBasedShipping`), `PaymentGateway`, `ProductTableReader` | Pricing, payment provider and file format vary independently of the use cases |
| Decorator | `FreeShippingOverThreshold` wraps any `ShippingPolicy`, `ResilientPaymentGateway` wraps any gateway | Adds free shipping, timeouts and retries without changing the wrapped code |
| Adapter | `SimulatedPaymentGateway`, `CsvProductTableReader` | Translate external formats and protocols into the application ports |
| Command and Handler | `CreateProductCommand` -> `CreateProduct`, `PlaceOrderCommand` -> `PlaceOrder` | Each use case has one input type and one entry point |
| Factory Method | `Product.create`, `Order.place`, `ProductDetails.build`, `create_app` | Construction enforces invariants, there is no way to build an invalid entity |
| Value Object | `Money`, `Sku`, `Customer`, `ShippingAddress`, `PaymentCard` | Validation and equality by value, no primitive obsession |
| Query Object / Specification | `ProductSearchCriteria` | Search inputs are validated once and translated by the read model |
| Notification | `FieldErrors` collector, `ImportReport` | Report every problem at once instead of failing on the first |
| CQRS (light) | `CatalogReadModel`, `OrderReadModel` for lists, repositories for writes | Read queries are optimized separately from aggregate persistence |
| Composition Root / Dependency Injection | `Container` | All wiring lives in one place, tests swap adapters there |
| Idempotent Receiver | `Idempotency-Key` on `POST /orders` | Retries of the same checkout never charge twice |
| Compensating action | `PlaceOrder` releases stock when the payment fails | Keeps stock correct without holding locks during the payment call |

## SOLID in practice

| Principle | Example |
|-----------|---------|
| Single Responsibility | `ImportProducts` orchestrates, `parse_product_row` converts text, `CsvProductTableReader` reads bytes, `ImportReportBuilder` collects outcomes |
| Open/Closed | A new shipping rule or payment provider is a new class plugged into the `Container`. A new error type gets its HTTP status by adding one entry to `PROBLEM_TYPES` |
| Liskov Substitution | In-memory fakes and SQLAlchemy repositories, and the simulated or resilient gateways, are interchangeable behind their ports: use case tests run on the fakes, integration tests run the same use cases on PostgreSQL |
| Interface Segregation | Separate ports for writes (`ProductRepository`) and reads (`CatalogReadModel`). `SearchProducts` depends only on the read model |
| Dependency Inversion | Use cases receive ports through their constructors. Only the composition root knows SQLAlchemy, uvicorn and the simulated gateway |

## API design

Base path `/api/v1`. Full schema at `/docs` (Swagger UI) and `/openapi.json`.

| Method | Path | Purpose | Success |
|--------|------|---------|---------|
| GET | `/categories` | Category values and labels | 200 |
| GET | `/products` | Search: `q`, `category`, `min_price`, `max_price`, `in_stock`, `sort`, `page`, `page_size` | 200 |
| POST | `/products` | Create a product | 201 + `Location` + `ETag` |
| GET | `/products/{id}` | Read a product | 200 + `ETag` |
| PATCH | `/products/{id}` | Partial update, optional `If-Match` | 200 + `ETag` |
| DELETE | `/products/{id}` | Archive (soft delete), optional `If-Match` | 204 |
| POST | `/product-imports` | Multipart CSV upload, `dry_run` query flag | 200 + import report |
| POST | `/checkout/quote` | Price a cart: subtotal, shipping, total | 200 |
| POST | `/orders` | Place an order, `Idempotency-Key` header required | 201, or 200 on replay |
| GET | `/orders` | List orders, optional `email` filter | 200 |
| GET | `/orders/{id}` | Read an order | 200 |
| GET | `/health/live`, `/health/ready` | Liveness and readiness probes | 200 / 503 |

Conventions:

- **Money is a decimal string** (`"89.99"`) with a separate `currency`, so JavaScript never rounds
  prices. Weights use 3 decimals.
- **Optimistic concurrency:** every product carries a `version`, returned as `ETag: "3"`. Sending
  `If-Match` makes stale updates fail with `412 Precondition Failed` instead of overwriting newer
  data. The admin UI always sends it.
- **Idempotency:** the client generates one key per checkout attempt. A retry with the same key and
  body returns the original order (`200`, `Idempotent-Replayed: true`). The same key with a
  different body is rejected with `422`, and a concurrent duplicate gets `409`.
- **Pagination** is page based (`page`, `page_size` up to 100) and returns `total` and
  `total_pages`, which suits the admin tables.
- **Resource oriented imports:** an import is a `POST` to `/product-imports` rather than an RPC
  style `/products/import`.
- **Operation ids** equal the Python function names (`place_order`, `search_products`), which keeps
  generated clients readable.

## Data validation

Validation happens in three layers, each with its own job:

1. **Edge (Pydantic schemas):** types, required fields, lengths, decimal places, enums and unknown
   fields (`extra="forbid"`). Limits come from domain constants, so the OpenAPI document is
   accurate.
2. **Domain (value objects and factories):** the business rules: SKU format, plain text without
   markup or control characters, price greater than 0 and at most 1,000,000, stock and weight
   ranges, email and postal code formats, Luhn check for cards, state machine for orders. The
   `FieldErrors` collector reports **all** invalid fields of a request or CSV row at once.
3. **Database:** `CHECK` constraints, a partial unique index on active SKUs, foreign keys and
   `NUMERIC` precision. These protect the data even from bugs or manual SQL.

The frontend mirrors the important rules with Zod schemas for instant feedback, but the server stays
the source of truth: its field errors are shown next to the matching inputs.

## Error handling

Every error response is `application/problem+json` (RFC 9457) with a stable machine readable `code`,
the `request_id` for support, and field level details when relevant:

```json
{
  "type": "urn:ecommerce:problem:insufficient_stock",
  "title": "Insufficient stock",
  "status": 409,
  "detail": "Not enough stock for: RS-001",
  "instance": "/api/v1/orders",
  "code": "insufficient_stock",
  "request_id": "5f0c6b1e2d7a4c41a0f3c8f1b6a9d2e4",
  "shortages": [{ "sku": "RS-001", "requested": 5, "available": 3 }]
}
```

| Error | Status | Code |
|-------|--------|------|
| Invalid input (edge or domain) | 422 | `validation_failed` |
| Unknown resource | 404 | `not_found` |
| SKU already exists | 409 | `duplicate_sku` |
| Not enough stock | 409 | `insufficient_stock` |
| Stale `If-Match` | 412 | `version_mismatch` |
| Card declined | 402 | `payment_declined` (with `order_id` and `decline_code`) |
| Payment provider down after retries | 502 | `payment_unavailable` |
| Same `Idempotency-Key`, different body | 422 | `idempotency_key_reused` |
| Same `Idempotency-Key` still processing | 409 | `request_in_progress` |
| Invalid CSV file (encoding, columns, quoting) | 422 | `invalid_import_file` |
| File or body too large | 413 | `import_limit_exceeded` / `payload_too_large` |
| Anything unexpected | 500 | `internal_error`, details only in the logs |

Domain and application errors know nothing about HTTP. The presentation layer maps exception
classes to statuses in one table (`PROBLEM_TYPES`), so adding an error never touches existing
handlers. API validation errors never echo the submitted values, so card numbers cannot leak into
responses or logs. The CSV report does quote the offending cell, truncated, to help fix the file.

## Purchase flow

```mermaid
sequenceDiagram
    autonumber
    participant UI as Web app
    participant API as PlaceOrder use case
    participant DB as PostgreSQL
    participant PSP as Payment gateway
    UI->>API: POST /orders + Idempotency-Key
    API->>DB: Find order by key (replay?)
    API->>DB: Tx 1: SELECT products FOR UPDATE, reserve stock, insert order PENDING_PAYMENT
    API->>PSP: Charge total (timeout + retries, same key)
    alt Approved
        API->>DB: Tx 2: mark order PAID
        API-->>UI: 201 Created
    else Declined or provider down
        API->>DB: Tx 2: mark order PAYMENT_FAILED, release stock
        API-->>UI: 402 or 502 problem with order id
    end
```

Design choices:

- **No locks are held while calling the payment provider.** Stock is reserved and committed in
  transaction 1, so slow payments do not block other shoppers. If the payment fails, transaction 2
  releases the stock (a compensating action).
- **Overselling is impossible.** Products are locked with `SELECT ... FOR UPDATE` in a consistent
  order, which prevents deadlocks. A `CHECK (stock >= 0)` constraint is the last line of defense.
  An integration test fires 10 concurrent checkouts at a product with 3 units: exactly 3 succeed.
- **Prices are snapshotted.** Order lines copy SKU, name, unit price and weight, so later catalog
  edits never change past orders. Archived products keep their history through soft delete.
- **Shipping is a strategy:** USD 4.99 plus USD 1.25 per started kilogram, free above USD 100 and
  for weightless goods. The values are configurable. The cart shows a server side quote, so the UI
  never computes the authoritative total.
- **Simulated provider:** cards are validated (Luhn, expiry, CVC). Only the brand, last 4 digits
  and provider reference are stored, never the full number or CVC.

Test cards (any future expiry and any 3 digit CVC):

| Card number | Outcome |
|-------------|---------|
| 4242 4242 4242 4242 | Approved (Visa) |
| 5555 5555 5555 4444 | Approved (Mastercard) |
| 4000 0000 0000 0259 | First attempt fails, the automatic retry succeeds |
| 4000 0000 0000 0002 | Declined: `card_declined` |
| 4000 0000 0000 9995 | Declined: `insufficient_funds` |
| 4000 0000 0000 0069 | Declined: `expired_card` |
| 4000 0000 0000 0127 | Declined: `incorrect_cvc` |
| 4000 0000 0000 0119 | Provider outage: 502 and the stock is released |

## Product search

`GET /api/v1/products?q=...` combines four PostgreSQL techniques in one indexed query:

- **Full-text search** on a generated, weighted `tsvector` (name and SKU weigh more than the
  description) with English stemming and prefix matching, so `runn` finds "Running Shoes";
- **Trigram similarity** (`pg_trgm`) on the name for typo tolerance, so `blutooth speker` finds
  "Bluetooth Speaker";
- **Substring match** on the name (`phone` finds "Phone Stand") and **prefix match** on the SKU
  (`rs-0`);
- **Filters** by category, price range and availability, and sorting by relevance, name, price or
  newest.

User input never reaches the `tsquery` syntax directly: it is tokenized into safe terms, and `LIKE`
wildcards are escaped, so `%` and `_` are searched literally.

## CSV import rules

- Required columns: `name, sku, description, category, price, stock, weight_kg`, in any order.
  Header names are case and space insensitive. Extra columns are ignored.
- UTF-8, optionally with a byte order mark. Up to 5 MB and 5,000 rows (configurable).
- Categories accept the label or the slug in any case: `Home & Office`, `home-office`.
- Upsert by SKU: new SKUs are created, existing ones updated, identical ones reported as unchanged.
- Duplicate SKUs within a file: the last occurrence wins, earlier ones are reported as superseded,
  exact repeats are reported as duplicates.
- Invalid rows are reported with every reason and skipped. Valid rows are written in **one
  transaction**, so an import never stops halfway.
- `dry_run=true` runs the full process, including database checks, and rolls back.
- The same use case runs from the UI, the API and the CLI (`ecommerce import-products file.csv`).

## Frontend

React 19 and TypeScript (strict), built with Vite and styled with Tailwind CSS.

| Library | Used for |
|---------|----------|
| TanStack Router | Type safe routes, search params validated with Zod (shareable search URLs), route loaders that prefetch data |
| TanStack Query | Server state, caching, request cancellation, retries only for network and 5xx errors |
| TanStack Table | Admin product table with server side sorting and pagination, orders table |
| TanStack Form | Product and checkout forms, validated with Zod schemas that mirror the server rules |
| TanStack Store | The cart, persisted to `localStorage` and validated when it is read |

Code is organized by **feature** (`catalog`, `cart`, `checkout`, `orders`, `imports`), each with its
API client, query options, components and pages. Shared code lives in `src/shared`.

UX details: debounced search-as-you-type, skeletons and empty states, a confirmation dialog for
deletes, toasts, inline server validation errors, test card shortcuts, a stale data warning on
concurrent edits (412), and a responsive layout down to phone width. Checkout keeps the same
idempotency key when a request fails on the network, so a retry can never charge twice.

In Docker the app is served by an unprivileged nginx that also proxies `/api` to the backend, so
the browser talks to one origin and the Content Security Policy can stay strict.

## Testing and quality gates

| Suite | Count | What it covers |
|-------|-------|----------------|
| Backend unit | 133 | Domain rules, use cases with in-memory adapters, CSV parsing (including the full sample file), payment simulation, retries, logging |
| Backend integration | 26 | Real PostgreSQL via Testcontainers: repositories, optimistic locking, constraints, search, concurrent checkout, imports, CLI |
| Backend API | 33 | HTTP behaviour end to end: status codes, headers, problem details, ETags, idempotency, uploads, limits |
| Frontend | 30 | Utilities, cart store, card helpers, Zod schemas, HTTP client, ProductForm component behaviour |

Backend gates: Ruff (lint and format), `mypy --strict`, `import-linter` architecture contracts and a
90% coverage threshold (currently 97%). Frontend gates: ESLint with type aware rules, Prettier,
`tsc` and Vitest. The CI workflow runs everything, builds both images, starts the Compose stack and
seeds it as a smoke test.

## Security notes

- No secrets in the repository. The database password is generated into a git ignored `.env`, and
  Compose refuses to start without it.
- The API and web containers run as non-root users with read-only file systems and
  `no-new-privileges`. The API and the database only listen on `127.0.0.1` on the host.
- Parameterized SQL everywhere, escaped `LIKE` patterns and sanitized full-text queries.
- Plain text policy for product data, plus React output escaping and a strict CSP on the web app.
- Request body limit, upload type and size checks, CSV row limits.
- Card data is validated and dropped after the charge: only brand, last 4 digits and the provider
  reference are stored. API errors and logs never contain submitted card values.
- Security headers on the API and the web app, and generic messages for unexpected errors.

## Configuration

Backend settings are environment variables with the `APP_` prefix
([`backend/src/ecommerce/infrastructure/config.py`](backend/src/ecommerce/infrastructure/config.py)).

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_DATABASE_URL` | required | `postgresql+asyncpg://user:password@host:5432/db` |
| `APP_CORS_ORIGINS` | `http://localhost:5173` | Comma separated allowed origins |
| `APP_LOG_LEVEL` / `APP_LOG_FORMAT` | `INFO` / `json` | Logging, `text` is handy locally |
| `APP_DOCS_ENABLED` | `true` | Serve `/docs` and `/openapi.json` |
| `APP_SHIPPING_BASE_FEE` / `APP_SHIPPING_PER_KG_FEE` / `APP_FREE_SHIPPING_THRESHOLD` | `4.99` / `1.25` / `100.00` | Shipping policy |
| `APP_PAYMENT_LATENCY_MS` / `APP_PAYMENT_TIMEOUT_SECONDS` / `APP_PAYMENT_MAX_ATTEMPTS` | `400` / `5` / `3` | Simulated provider and resilience |
| `APP_IMPORT_MAX_BYTES` / `APP_IMPORT_MAX_ROWS` | `5242880` / `5000` | Import limits |

Compose reads `POSTGRES_PASSWORD` (required), `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PORT`,
`API_PORT` and `WEB_PORT` from the root `.env` ([`.env.example`](.env.example)).

## Alternatives considered

| Topic | Chosen | Alternatives and why not |
|-------|--------|--------------------------|
| Architecture | Clean Architecture | Layered: simpler, but couples rules to the ORM. Vertical slices: great for many small features, less clear for shared rules like stock |
| Database | PostgreSQL | MongoDB: see the comparison above |
| Data access | SQLAlchemy 2 async with explicit mappers | Imperative mapping onto domain classes: less code, but leaks ORM state into entities. SQLModel: mixes API and persistence models |
| Migrations | Alembic, run as a one-off Compose job | Migrating on API start: races when several replicas start together |
| Categories | Closed enum plus a `CHECK` constraint | Lookup table: better when the business edits categories, would need its own CRUD. Native PostgreSQL enum: painful to alter |
| Product delete | Soft delete (archive) | Hard delete: breaks order history or needs nullable foreign keys |
| Duplicate SKUs in a file | Last row wins, reported | First wins, or reject the whole file: both lose the "Updated" intent of the sample data |
| Invalid CSV rows | Skip and report, valid rows in one transaction | All-or-nothing: one typo blocks 5,000 rows. Dry run covers the strict use case |
| Large imports | Synchronous, with limits | Background job with a queue (Celery, arq) and an import status resource, the next step for big files |
| Search | PostgreSQL FTS and trigrams | Elasticsearch or OpenSearch: better relevance tuning, but another system to run and keep in sync |
| Pagination | Page and size | Cursor (keyset) pagination: scales better for infinite scroll, but tables need page numbers |
| Concurrency | Pessimistic locks for stock, optimistic `ETag` for edits | Optimistic only: retries under heavy checkout contention. Atomic `UPDATE ... WHERE stock >= n`: fast, but harder with multi-line orders and reporting |
| Payment call | Outside the stock transaction, with compensation | Inside the transaction: simpler, but holds row locks during network calls |
| Card handling | Card data sent to the simulated gateway | Real setup: provider hosted fields and tokens, so card numbers never reach the backend (PCI SAQ A) |
| Frontend routing | TanStack Router, code based routes | File based routes: generated route tree. React Router: less type safety for search params |
| Frontend types | Hand written TypeScript types | Generated from OpenAPI with `openapi-typescript`: worth it once the API grows |
| Styling | Tailwind CSS with small own components | A component library (MUI, shadcn/ui): faster for large apps, more dependencies |
| Packaging | Compose with separate API and web images | One image serving the SPA from FastAPI: fewer moving parts, but couples deployments |

## Known limitations and next steps

- **Authentication and authorization** are out of scope. The next step is OIDC (for example
  Keycloak or Auth0), JWT validation as a FastAPI dependency, and an admin role for catalog and
  import endpoints.
- **Stuck reservations:** if the process dies between reserving stock and settling the payment, the
  order stays `pending_payment`. A scheduled job should expire old pending orders and release their
  stock. With a real provider, payment webhooks and an outbox table would make this reliable.
- **Background imports** with progress reporting for files larger than the synchronous limit.
- **Observability:** OpenTelemetry traces and Prometheus metrics on top of the existing request ids
  and JSON logs.
- **Catalog features:** images, discounts and promotions, multi currency and taxes.
- **End to end tests** with Playwright in CI. The flows were verified manually with a headless
  browser during development.
