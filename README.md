# E-commerce Platform

A full stack e-commerce application built as if it were a real corporate project: a **FastAPI**
backend designed with **Clean Architecture**, a **PostgreSQL** database, and a **React +
TypeScript + TanStack** frontend, packaged as a **Docker Compose** monorepo.

---

## Contents

1. [Highlights](#highlights)
2. [Quick start with Docker](#quick-start-with-docker)
3. [Local development](#local-development)
4. [The sample CSV](#the-sample-csv)
5. [Approach](#approach)
6. [Architecture: Clean vs Layered](#architecture-clean-vs-layered)
7. [Database: PostgreSQL vs MongoDB](#database-postgresql-vs-mongodb)
8. [Database design](#database-design)
9. [Design patterns and SOLID](#design-patterns-and-solid)
10. [API design](#api-design)
11. [Data validation](#data-validation)
12. [Error handling](#error-handling)
13. [Purchase flow](#purchase-flow)
14. [Product search](#product-search)
15. [CSV import rules](#csv-import-rules)
16. [Product images](#product-images)
17. [Frontend](#frontend)
18. [Dark and light mode](#dark-and-light-mode)
19. [Testing and quality gates](#testing-and-quality-gates)
20. [Security notes](#security-notes)
21. [Configuration](#configuration)
22. [Alternatives considered](#alternatives-considered)
23. [Known limitations and next steps](#known-limitations-and-next-steps)

## Highlights

| Area | What is implemented |
|------|---------------------|
| Product CRUD | Create, read, partial update and soft delete, with optimistic concurrency (`ETag` / `If-Match`) |
| CSV import | Upload or CLI, row level report, dry run, upsert by SKU, duplicate detection, one transaction, optional image URL columns |
| Product images | Optional per product. Uploaded or imported from a URL (SSRF safe), validated and normalized server side, AVIF and WebP in 5 widths, content hashed immutable URLs, blur-up placeholders, responsive `<picture>`, photo credits |
| Search | PostgreSQL full-text search plus trigram fuzzy matching, filters, sorting and pagination |
| Purchase | Cart, server side quote, weight based shipping, simulated card payments, idempotent checkout |
| API | Versioned REST, RFC 9457 Problem Details, OpenAPI docs, request ids, size limits |
| Frontend | TanStack Router, Query, Table, Form and Store, Zod validation, Tailwind CSS |
| Theming | Light, dark and system themes from semantic design tokens, no flash on load, CSP friendly |
| Quality | Unit, integration (real PostgreSQL via Testcontainers) and API tests, frontend tests, `mypy --strict`, architecture contracts, CI |
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
sample products and downloads their photos, which needs internet access (see
[Sample photos](#sample-photos)).

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

Requirements: Python 3.13 with [uv](https://docs.astral.sh/uv/) (uv downloads it if needed),
Node.js 22.12 or newer (`nvm use` reads the version from `.nvmrc`), Docker (for PostgreSQL and for
the integration tests).

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
and `/media` to the backend, so no CORS setup is needed. Then load the sample data:

```bash
make dev-seed
```

Local development uses the same database volume as the Docker stack, but stores images in
`backend/var/media` instead of the `media` volume. Photos imported by one are not visible to the
other, and re-importing reports them as unchanged, so run `make clean` before switching.

Quality checks, the same ones CI runs:

```bash
make check
```

The backend integration and API tests start a disposable PostgreSQL container with Testcontainers.
To reuse an existing database instead, export `TEST_DATABASE_URL`, for example
`postgresql+asyncpg://user:password@localhost:5432/ecommerce_test`. The tests reset its schema.

## The sample CSV

The provided example file was **downloaded on October 17, 2026**. It is stored
unchanged in [`data/products-sample.csv`](data/products-sample.csv).
A copy with photo columns gives the same results (see [Sample photos](#sample-photos)).

It has 97 data rows with deliberate data quality problems. This is how each one is handled.
Line numbers include the header, so they match what a spreadsheet shows.

| Line | SKU | Problem in the data | Decision | Result |
|------|-----|---------------------|----------|--------|
| 4 | WM-042 | Price `$29.99` | A leading `$` is unambiguous for a USD catalog, so it is stripped and reported | Created, with a note |
| 7 | YM-015 | Price `free` | Never guess a price | Failed |
| 16 | DL-007 | Stock `-5` | Stock cannot be negative | Failed |
| 20 | XS-001 | Name `<script>alert('xss')</script>` | Text fields are plain text, markup is rejected (React also escapes output) | Failed |
| 25 | HD-099 | Empty name | Name is required | Failed |
| 29 | SQL-001 | Name `Robert'); DROP TABLE products;--` | Harmless to the database (parameterized SQL), but it is an attack payload, not a product name, so a domain rule rejects it | Failed |
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

Summary: **83 created, 5 skipped, 9 failed**. Importing the same file again reports 83 unchanged
rows, so the import is idempotent.

### Why the SQL-001 row is rejected

Parameterized queries already make this name harmless to the database, and they remain the real
defense. The row is still rejected because an attack payload is bad catalog data that could hurt a
less careful consumer later, so a domain rule (`reject_sql_payload` in `domain/text.py`, mirrored in
the product form) rejects SQL statement shapes such as `'); DROP TABLE` or `' OR '1'='1`, while
names like "Drop Earrings" or "Robert's Running Shoes" stay valid.

## Approach

Model the business first, with self-validating domain objects and the CSV quirks as explicit, tested
rules. Expose every feature as a use case (`CreateProduct`, `ImportProducts`, `PlaceOrder`) that
FastAPI and the CLI only adapt. Let PostgreSQL enforce constraints and power search. Treat failures
as designed outcomes with stable error codes. Ship it operable: migrations as a job, health probes,
JSON logs with request ids, non-root containers and a CI pipeline that boots the stack.

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
- **Testability drove the design.** Domain and use case tests run without a database on
  in-memory adapters, while integration tests prove the adapters against a real PostgreSQL.

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
|   |   |-- infrastructure/    adapters: persistence, payments, images, storage, files, config
|   |   |-- presentation/api/  FastAPI app, routers, schemas, middleware, problem details
|   |   |-- container.py       composition root (dependency injection)
|   |   `-- cli.py             operational commands (CSV import, used by the seed job)
|   |-- migrations/            Alembic migrations
|   `-- tests/                 unit, integration (PostgreSQL) and API tests
|-- frontend/
|   |-- src/app/               router, layout, query client
|   |-- src/features/          catalog, cart, checkout, orders, imports (feature folders)
|   |-- src/shared/            HTTP client, UI components, formatting and form helpers
|   `-- nginx/                 production web server config
|-- data/
|   |-- products-sample.csv         the provided example file, unchanged
|   `-- products-sample-images.csv  the same rows plus image URL and photo credit columns
|-- docker-compose.yml         db, migrate, api, web and seed services
|-- Makefile                   one entry point for every workflow
`-- .github/workflows/ci.yml   lint, types, tests, build, and a Compose smoke test
```

## Database: PostgreSQL vs MongoDB

**Decision: PostgreSQL 17.**

| Criterion | PostgreSQL (chosen) | MongoDB |
|-----------|---------------------|---------|
| Shape of the data | Uniform product schema, orders with lines that reference products: relational | Flexible documents, best when product attributes vary a lot |
| Checkout consistency | ACID transactions across products and orders | Multi-document transactions need a replica set and are more limited |
| Money | Exact `NUMERIC(12,2)` | `Decimal128`, workable but less common in drivers and tooling |
| Integrity at rest | `CHECK` constraints, unique and foreign keys | Schema validation is optional and weaker |
| Search | Built-in full-text search (`tsvector`, GIN) and `pg_trgm` fuzzy matching | Text indexes (no fuzzy matching) or Atlas Search, which is a managed service |
| Operations | Alembic migrations, mature backups and tooling | Schemaless evolution, but migrations still exist in practice |

MongoDB would win for a catalog with highly heterogeneous attributes per category. If that need
appears, PostgreSQL `JSONB` columns cover it without giving up transactions.

## Database design

Three tables in PostgreSQL 17, created by Alembic migrations
([`backend/migrations`](backend/migrations)) that match the SQLAlchemy models in
[`models.py`](backend/src/ecommerce/infrastructure/persistence/models.py). Domain entities never
see these classes: explicit mappers translate in both directions.

```mermaid
erDiagram
    products ||--o{ order_lines : "is sold as"
    orders ||--|{ order_lines : contains

    products {
        uuid id PK
        varchar(32) sku UK "unique while archived_at is null"
        varchar(200) name
        varchar(2000) description
        varchar(40) category "CHECK known category"
        numeric price "12,2 - CHECK price > 0"
        varchar(3) currency
        integer stock "CHECK stock >= 0"
        numeric weight_kg "8,3 - CHECK weight_kg >= 0"
        jsonb image "nullable - CHECK is an object"
        tsvector search_vector "generated - GIN index"
        integer version "optimistic lock"
        timestamptz created_at "indexed"
        timestamptz updated_at
        timestamptz archived_at "nullable - soft delete"
    }

    orders {
        uuid id PK
        varchar(16) number UK "ORD- plus 12 symbols from the id"
        varchar(20) status "CHECK pending_payment, paid, payment_failed"
        varchar(120) customer_name
        varchar(254) customer_email "indexed"
        varchar(200) shipping_line1
        varchar(100) shipping_city
        varchar(15) shipping_postal_code
        varchar(2) shipping_country
        varchar(3) currency
        numeric subtotal "12,2"
        numeric shipping_cost "12,2"
        numeric total "12,2 - CHECK total = subtotal + shipping_cost"
        numeric total_weight_kg "12,3"
        varchar(100) idempotency_key UK
        varchar(64) request_fingerprint "SHA-256 of the request"
        varchar(64) payment_reference "nullable"
        varchar(20) card_brand "nullable"
        varchar(4) card_last4 "nullable"
        varchar(40) payment_failure_code "nullable"
        integer version "optimistic lock"
        timestamptz created_at "indexed"
        timestamptz updated_at
    }

    order_lines {
        uuid order_id PK, FK "ON DELETE CASCADE"
        integer position PK
        uuid product_id FK "ON DELETE RESTRICT - indexed"
        varchar(32) sku "snapshot"
        varchar(200) name "snapshot"
        numeric unit_price "12,2 - snapshot"
        integer quantity "CHECK quantity > 0"
        numeric unit_weight_kg "8,3 - snapshot"
        numeric line_total "12,2"
    }
```

Types are PostgreSQL types, and `numeric` precision and scale are in the notes. Every column is
`NOT NULL` unless marked nullable.

Design decisions:

- **Keys.** UUIDs are generated by the application, so an entity has its identity before it is
  saved, ids cannot be guessed or enumerated, and bulk imports need no round trip per row. The
  short, unique order `number` that customers see is derived from the id.
- **Value objects as columns.** Customer, shipping address, totals and payment outcome are 1:1
  with the order and never queried on their own, so they are columns of `orders`, not tables.
- **Money and weights** are `NUMERIC`, never floats, with an explicit `currency` column. The
  `total_consistent` check makes the database itself reject an order whose total does not add up.
- **Snapshots for history.** Order lines copy SKU, name, unit price and weight at purchase time.
  Editing or archiving a product never rewrites past orders, while `product_id` still links back
  for reporting.
- **Soft delete with a partial unique index.** `uq_products_sku_active` enforces unique SKUs only
  where `archived_at IS NULL`, so an archived SKU can be reused and its old row stays for order
  lines.
- **Concurrency.** `version` is a SQLAlchemy `version_id_col`: each update runs
  `UPDATE ... WHERE id = :id AND version = :expected` and fails if another writer got there first.
  The API exposes it as the `ETag`.
- **Integrity at rest.** Named `CHECK` constraints mirror the domain rules: `price_positive`,
  `stock_non_negative`, `weight_non_negative`, `category_known`, `image_is_object`,
  `status_known`, `total_consistent` and `quantity_positive`. All constraints and indexes follow one
  naming convention (`pk_`, `fk_`, `uq_`, `ck_`, `ix_`), so migrations stay predictable.
- **Search.** `search_vector` is a stored generated column (name and SKU weighted A, description
  weighted B) with a GIN index. A `pg_trgm` GIN index on `name` powers fuzzy matching for typos.
- **The optional image is a JSONB document**, not a table: it is metadata about files in object
  storage, there is at most one per product, and it is always read with the product.
- **No customers table yet.** Checkout is a guest flow, so the customer belongs to the order. With
  authentication, a `customers` table and an `orders.customer_id` foreign key would be added, and
  the address columns would stay as a snapshot of where that order was shipped.

## Design patterns and SOLID

| Pattern | Where | Why |
|---------|-------|-----|
| Repository | `ProductRepository`, `OrderRepository` ports, SQLAlchemy adapters and in-memory test fakes | Use cases talk about aggregates, not SQL |
| Unit of Work | `UnitOfWork` port, `SqlAlchemyUnitOfWork` | One transaction per business operation, explicit commit, automatic rollback |
| Data Mapper | `ProductMapper`, `OrderMapper` | Domain entities stay free of ORM state, the ORM records stay free of rules |
| Strategy | `ShippingPolicy` (`WeightBasedShipping`), `PaymentGateway`, `ProductTableReader`, `ObjectStorage` (local disk or S3) | Pricing, payment provider, file format and storage vary independently of the use cases |
| Decorator | `FreeShippingOverThreshold` wraps any `ShippingPolicy`, `ResilientPaymentGateway` wraps any gateway | Adds free shipping, timeouts and retries without changing the wrapped code |
| Adapter | `SimulatedPaymentGateway`, `CsvProductTableReader`, `PillowImageProcessor`, `S3ObjectStorage` | Translate external libraries, formats and protocols into the application ports |
| Value Object | `Money`, `Sku`, `Customer`, `ShippingAddress`, `PaymentCard` | Validation and equality by value, no primitive obsession |
| CQRS (light) | `CatalogReadModel`, `OrderReadModel` for lists, repositories for writes | Read queries are optimized separately from aggregate persistence |
| Composition Root / Dependency Injection | `Container` | All wiring lives in one place, tests swap adapters there |

| Principle | Example |
|-----------|---------|
| Single Responsibility | `ImportProducts` orchestrates, `parse_product_row` converts text, `CsvProductTableReader` reads bytes |
| Open/Closed | New shipping rules, gateways or error types plug in without editing the use cases |
| Liskov Substitution | In-memory fakes and SQLAlchemy repositories are interchangeable behind the same ports |
| Interface Segregation | Separate write (`ProductRepository`) and read (`CatalogReadModel`) ports |
| Dependency Inversion | Use cases depend on ports, only the `Container` knows the concrete adapters |

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
| PUT | `/products/{id}/image` | Upload or replace the image (multipart), optional `If-Match` | 200 + `ETag` |
| PUT | `/products/{id}/image/from-url` | Download, process and attach an image from an https URL, optional credit and `If-Match` | 200 + `ETag` |
| DELETE | `/products/{id}/image` | Remove the image, optional `If-Match` | 200 + `ETag` |
| POST | `/product-imports` | Multipart CSV upload with optional image columns, `dry_run` query flag | 200 + import report |
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

## Data validation

Validation happens in three layers, each with its own job:

1. **Edge (Pydantic schemas):** types, required fields, lengths, decimal places, enums and unknown
   fields (`extra="forbid"`). Limits come from domain constants, so the OpenAPI document is
   accurate.
2. **Domain (value objects and factories):** the business rules: SKU format, plain text without
   markup, control characters or SQL injection payloads, price greater than 0 and at most 1,000,000, stock and weight
   ranges, email and postal code formats, Luhn check for cards, state machine for orders. The
   `FieldErrors` collector reports **all** invalid fields of a request or CSV row at once.
3. **Database:** constraints, keys and `NUMERIC` precision protect the data even from bugs or
   manual SQL (see [Database design](#database-design)).

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
| File or body too large | 413 | `import_limit_exceeded` / `image_too_large` / `payload_too_large` |
| Not a JPEG, PNG, WebP or AVIF image | 415 | `unsupported_image_type` |
| Corrupted, truncated or too small image | 422 | `invalid_image` |
| Image URL not https, private network address, wrong port or host | 422 | `invalid_image_source` |
| Image URL unreachable, not 200, timed out or too many redirects | 502 | `image_source_unavailable` |
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
- **Shipping is a strategy:** USD 4.99 plus USD 1.25 per started kilogram, free above USD 100 and
  for weightless goods. The values are configurable. The cart shows a server side quote, so the UI
  never computes the authoritative total.
- **Simulated provider:** cards are validated (Luhn, expiry, CVC).

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
- Optional image columns: `image_url, image_author, image_license, image_license_url,
  image_source_url`. They are validated with the rest of the row: `image_url` must be an http(s)
  URL, and a credit needs the author, the license and the source page.
- Images are downloaded **after** the products are committed, through the SSRF safe fetcher with up
  to 4 downloads at a time, and processed exactly like an upload. Each row reports its image as
  `attached`, `unchanged` or `failed`. A failed download is reported on its row and never undoes
  the product.
- A product whose image already came from the same URL is `unchanged` and is not downloaded again,
  so re-importing a file is cheap. An empty `image_url` leaves the current image alone: an import
  never removes images. A dry run validates the image columns but downloads nothing.
- The same use case runs from the UI, the API and the CLI (`ecommerce import-products file.csv`).

## Product images

The image is **optional**: a product without a photo shows a neutral placeholder, and an admin can
add, replace or remove it at any time from the product edit page, either by uploading a file or by
pasting an image URL. In the database it is one nullable `JSONB` column with the image metadata
(including the origin URL and the photo credit when there is one), while the files live in object
storage.

```mermaid
flowchart LR
    A["Admin drops a file"] --> B["Browser: type and size check,<br/>downscale above 2560 px, preview"]
    B -->|"PUT /products/{id}/image<br/>multipart + If-Match, progress bar"| C["API: size limit,<br/>format from magic bytes"]
    U["Admin pastes a URL,<br/>or a CSV image_url column"] -->|"PUT /products/{id}/image/from-url"| R["SSRF safe fetcher:<br/>https, public IPs, size and time limits"]
    R --> C
    C --> D["Pillow in a worker thread:<br/>EXIF orientation, sRGB, strip metadata"]
    D --> E["5 widths x AVIF + WebP<br/>+ 24 px blur placeholder"]
    E --> F["Object storage:<br/>content hashed keys"]
    F --> G["PostgreSQL:<br/>image metadata (JSONB)"]
```

### Uploading

- The browser checks the type and size, shows a preview and downscales photos above 2560 px or
  3 MB before uploading, with a progress bar.
- The server detects the format from the bytes (JPEG, PNG, WebP or AVIF, never SVG), rejects
  decompression bombs, truncated files and images under 200 px, applies the EXIF orientation,
  converts to sRGB and strips all metadata.
- Widths 160 to 1280 px are encoded as AVIF and WebP in worker threads, stored under content hashed
  keys and served with `Cache-Control: immutable`, so caches never need purging.
- Files are written before the product row is updated (with `If-Match`). A failed update deletes
  the new files, and replaced files are cleaned up afterwards.

### Importing from a URL

`PUT /products/{id}/image/from-url` takes `{url, credit?}`. The **server** downloads the file and
sends the bytes through exactly the same validation and rendition pipeline as an upload, so a
remote image ends up as local AVIF and WebP files with immutable URLs. Customers never load the
third party URL: there is no hotlinking, the CSP keeps `img-src` on the shop's own origin, a remote site going down
or changing the photo does not break the shop, and visitors are not tracked by other hosts.

Fetching a URL chosen by a user is a classic **SSRF** risk (making the server call
`http://169.254.169.254/` or an internal admin panel), so `HttpImageFetcher` is strict:

- only `https`, the default port, and no credentials in the URL;
- the host is resolved and **every address must be public** (`ipaddress.is_global`), which blocks
  loopback, private ranges, link-local cloud metadata, CGNAT, multicast and IPv6 equivalents;
- redirects are followed manually, at most 3, and every hop is checked again, so a public URL
  cannot bounce to an internal one;
- connect and read timeouts, a `Content-Length` check and a streamed byte limit
  (`APP_IMAGE_MAX_BYTES`), and an `image/*` content type are required;
- an optional host allow list (`APP_IMAGE_FETCH_ALLOWED_HOSTS`) for production, where only known
  CDNs or a DAM should be reachable.

`APP_IMAGE_FETCH_ALLOW_HTTP` and `APP_IMAGE_FETCH_ALLOW_PRIVATE_NETWORKS` exist only for local
development and tests (for example a MinIO bucket on `localhost`).

Transient failures (`429`, `502` to `504` and network errors) get up to 3 attempts, honouring
`Retry-After`. Some hosts, such as Wikimedia Commons, also require contact details in
`APP_IMAGE_FETCH_USER_AGENT`.

### Loading and showing

- The API returns `image: {url, width, height, placeholder, sources, credit}`, with AVIF and WebP
  `srcset`s built from `APP_MEDIA_BASE_URL` (a CDN in production).
- The UI renders a responsive `<picture>` with a `sizes` value per context, reserved dimensions (no
  layout shift), lazy loading below the fold and high priority for the first visible images.
- A 24 px blur placeholder is inlined as a data URI, and photo credits are shown under the photo
  with safe `rel` links, as CC BY licenses require.
- nginx serves `/media/` from the storage volume with immutable caching.

### Storage backends

`APP_MEDIA_BACKEND=local` (the default) writes to a directory. In Docker that is a volume shared
read-only with nginx. `APP_MEDIA_BACKEND=s3` uses any S3 compatible service, configured with
`APP_S3_BUCKET`, `APP_S3_ENDPOINT_URL` and `APP_S3_REGION` plus the standard AWS credential
chain. It sets the content type and the immutable cache header on every object. Both adapters
implement the same `ObjectStorage` port and are selected in the composition root.

### Sample photos

The repository contains **no image binaries**.
[`data/products-sample-images.csv`](data/products-sample-images.csv) is the provided sample file
with the five optional [image columns](#csv-import-rules) appended to every line. The original text
of each line is untouched, so line numbers, quoting and every data quality problem stay exactly the
same.

The 83 photos were found through the Openverse catalog and are CC0, public domain, CC BY or CC
BY-SA, hosted on Flickr, rawpixel, StockSnap and the WordPress photo directory. Rows that fail validation and
blank rows have empty image columns. Superseded duplicates carry the same photo as the row that
wins, so duplicate handling is unchanged.

`make seed` runs `ecommerce import-products /data/products-sample-images.csv`. Running it again
reports 83 unchanged products and 83 unchanged images, and downloads nothing.

One file keeps each product and its photo on the same line, needs one command and gives one
report, and it is the same format an admin can upload on the Import page.

## Frontend

React 19 and TypeScript (strict), built with Vite and styled with Tailwind CSS.

| Library | Used for |
|---------|----------|
| TanStack Router | Type safe routes, search params validated with Zod (shareable search URLs), route loaders that prefetch data |
| TanStack Query | Server state, caching, request cancellation, retries only for network and 5xx errors |
| TanStack Table | Admin product table with server side sorting and pagination, orders table |
| TanStack Form | Product and checkout forms, validated with Zod schemas that mirror the server rules |
| TanStack Store | The cart and the theme preference, persisted to `localStorage` and validated when read |

Code is organized by **feature** (`catalog`, `cart`, `checkout`, `orders`, `imports`), each with its
API client, query options, components and pages. Shared code lives in `src/shared`.

UX details: debounced search-as-you-type, skeletons and empty states, a confirmation dialog for
deletes, drag and drop image upload with preview and progress, toasts, inline server validation errors, test card shortcuts, a stale data warning on
concurrent edits (412), and a responsive layout down to phone width.

In Docker the app is served by an unprivileged nginx that also proxies `/api` to the backend, so
the browser talks to one origin and the Content Security Policy can stay strict.

## Dark and light mode

Light, dark and system themes (the default follows `prefers-color-scheme`), chosen in the header and
remembered locally. Colors are semantic CSS variables registered as Tailwind theme tokens, and a
small static script sets the theme before the first paint, so there is no flash and the CSP needs
no inline scripts.

## Testing and quality gates

| Suite | Count | What it covers |
|-------|-------|----------------|
| Backend unit | 225 | Domain rules, use cases on in-memory adapters, CSV parsing, image processing, URL fetcher, storage, payments |
| Backend integration | 31 | Real PostgreSQL via Testcontainers: repositories, locking, constraints, migrations, search, concurrent checkout, imports, CLI |
| Backend API | 48 | HTTP end to end: status codes, headers, problem details, ETags, idempotency, imports, images, limits |
| Frontend | 47 | Stores, helpers, Zod schemas, HTTP client, components and forms |

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
- Plain text policy for product data (no markup, no SQL injection payloads), plus React output
  escaping and a strict CSP on the web app.
- Server side URL imports are protected against SSRF, see [Importing from a URL](#importing-from-a-url).
- Request body limit, upload type and size checks, CSV row limits.
- Uploaded images are identified by their bytes, re-encoded from decoded pixels (so polyglot files
  and embedded payloads do not survive), limited in pixels against decompression bombs, and
  stripped of EXIF and GPS metadata. SVG is never accepted.
- Storage keys are generated by the server and validated against path traversal. Media is served
  with `nosniff` and explicit image MIME types.
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
| `APP_MEDIA_BACKEND` | `local` | `local` directory or `s3` compatible object storage |
| `APP_MEDIA_ROOT` / `APP_MEDIA_BASE_URL` / `APP_MEDIA_SERVE` | `var/media` / `/media` / `false` | Local storage path, public URL prefix (a CDN in production), let the API serve files in development |
| `APP_S3_BUCKET` / `APP_S3_ENDPOINT_URL` / `APP_S3_REGION` | none / none / `us-east-1` | S3, R2 or MinIO settings when the backend is `s3` |
| `APP_IMAGE_FETCH_ALLOWED_HOSTS` | empty (any public host) | Comma separated host allow list for URL imports, subdomains included |
| `APP_IMAGE_FETCH_USER_AGENT` | `EcommercePlatform/1.0 (product image import)` | User agent for image downloads, add contact details for hosts that require them |

Shipping fees, the payment simulation, import and image limits, and the image download timeout,
retries and development switches are configurable too. Every setting and its default is in
[`config.py`](backend/src/ecommerce/infrastructure/config.py).

Compose reads `POSTGRES_PASSWORD` (required), `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PORT`,
`API_PORT` and `WEB_PORT` from the root `.env` ([`.env.example`](.env.example)).

## Alternatives considered

| Topic | Chosen | Alternatives and why not |
|-------|--------|--------------------------|
| Data access | SQLAlchemy 2 async with explicit mappers | Imperative mapping onto domain classes: less code, but leaks ORM state into entities. SQLModel: mixes API and persistence models |
| Migrations | Alembic, run as a one-off Compose job | Migrating on API start: races when several replicas start together |
| Categories | Closed enum plus a `CHECK` constraint | Lookup table: better when the business edits categories, would need its own CRUD. Native PostgreSQL enum: painful to alter |
| Duplicate SKUs in a file | Last row wins, reported | First wins, or reject the whole file: both lose the "Updated" intent of the sample data |
| Invalid CSV rows | Skip and report, valid rows in one transaction | All-or-nothing: one typo blocks 5,000 rows. Dry run covers the strict use case |
| Search | PostgreSQL FTS and trigrams | Elasticsearch or OpenSearch: better relevance tuning, but another system to run and keep in sync |
| Pagination | Page and size | Cursor (keyset) pagination: scales better for infinite scroll, but tables need page numbers |
| Concurrency | Pessimistic locks for stock, optimistic `ETag` for edits | Optimistic only: retries under heavy checkout contention. Atomic `UPDATE ... WHERE stock >= n`: fast, but harder with multi-line orders and reporting |
| Payment call | Outside the stock transaction, with compensation | Inside the transaction: simpler, but holds row locks during network calls |
| Card handling | Card data sent to the simulated gateway | Real setup: provider hosted fields and tokens, so card numbers never reach the backend (PCI SAQ A) |
| Frontend routing | TanStack Router, code based routes | File based routes: generated route tree. React Router: less type safety for search params |
| Frontend types | Hand written TypeScript types | Generated from OpenAPI with `openapi-typescript`: worth it once the API grows |
| Styling | Tailwind CSS with small own components | A component library (MUI, shadcn/ui): faster for large apps, more dependencies |
| Repository layout | Monorepo, each app with its own toolchain and Dockerfile | Separate repositories: independent releases, but an API change needs coordinated pull requests and CI runs |
| Packaging | Compose with separate API and web images | One image serving the SPA from FastAPI: fewer moving parts, but couples deployments |
| Image upload path | Multipart upload through the API | Presigned direct-to-S3 uploads: no upload traffic on the API, best for large or very frequent files, but needs storage CORS and an asynchronous finalize step. The next step at scale |
| Image processing | Renditions generated once at upload | On the fly image service (imgproxy, Thumbor, Cloudinary, Imgix) behind a CDN: any size on demand, but another service or vendor to run and pay for |
| Image storage | Object storage, metadata in a `JSONB` column | Images in PostgreSQL `BYTEA`: simple, but bloats the database and backups and cannot sit behind a CDN. A `product_images` table: needed for galleries, more than one optional image needs |
| Sample photos | Image URL columns in a copy of the sample CSV, downloaded and processed on import | Commit the binaries: works offline, but 8.6 MB of history that never shrinks. Git LFS: smaller clones, but needs LFS on every machine and in CI. Hotlink the remote URLs in `<img>`: zero storage, but no AVIF or sizes, a looser CSP, third party tracking and broken images when the source changes. An image proxy (imgproxy) in front of remote URLs: on demand sizes, but another service and the same availability risk |
| Image formats | AVIF with WebP fallback | Adding JPEG: every current browser supports WebP, so it would only add storage |
| Image placeholder | Inline 24 px WebP data URI | BlurHash or ThumbHash: smaller strings, but they need JavaScript to decode. A dominant color: cheaper, less pleasant |

## Known limitations and next steps

- **Authentication and authorization** are out of scope. The next step is OIDC (for example
  Keycloak or Auth0), JWT validation as a FastAPI dependency, and an admin role for catalog and
  import endpoints.
- **Stuck reservations:** if the process dies between reserving stock and settling the payment, the
  order stays `pending_payment`. A scheduled job should expire old pending orders and release their
  stock. With a real provider, payment webhooks and an outbox table would make this reliable.
- **Background imports** with progress reporting for files larger than the synchronous limit and
  for files with many image URLs. Today the request waits for the downloads, and nginx allows 5
  minutes on the import endpoint.
- **Observability:** OpenTelemetry traces and Prometheus metrics on top of the existing request ids
  and JSON logs.
- **Catalog features:** image galleries and editable alt text, discounts and promotions, multi
  currency and taxes.
- **URL imports:** the SSRF checks run before connecting, which leaves a small DNS rebinding
  window. Pinning the resolved IP in the HTTP transport, or an egress proxy, would close it.
- **Orphaned media:** if the process dies between storing the files and updating the product, the
  files remain unreferenced. A periodic job comparing storage keys with the database would clean
  them up.
- **End to end tests** with Playwright in CI, covering the main flows, image delivery and both
  themes.
