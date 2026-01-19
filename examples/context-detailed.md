# Project Context

## Architecture
This is a microservices-based e-commerce backend built with FastAPI and PostgreSQL. Services communicate via RabbitMQ (asynchronous) and gRPC (synchronous). The `gateway` service handles authentication and routing, while `orders`, `inventory`, and `users` manage their respective domains.

## Decisions
- **FastAPI for Services**: Selected for high performance (async support) and automatic OpenAPI documentation generation.
  - *Context*: Replaces legacy Flask app.
  - *Alternatives*: Django (too heavy), Flask (no native async).
- **RabbitMQ for Events**: Used for "Order Placed" -> "Inventory Reserved" flow to decouple critical path.
  - *Rationale*: Guarantees message delivery even if `inventory` service is down.
- **SQLAlchemy ORM**: Used for database interactions.
  - *Pattern*: Repository pattern used to abstract DB logic from service layer.
- **JWT Authentication**: Stateless auth tokens signed with RS256.
  - *Reason*: Allows independent scaling of auth service; gateways can verify without DB lookup.
- **Poetry for Dependency Management**: Enforces strict version locking.
  - *Context*: Solved previous "works on my machine" issues with `pip freeze`.

## Key Symbols
- `ServiceBase`: Abstract base class in `common/` that all services inherit from. Handles logging setup and config loading.
- `EventPublisher`: Wrapper around `aio_pika` for publishing domain events.
- `DependencyContainer`: Implements dependency injection for services.
- `OrderRepository`: Data access layer for order storage.

## Patterns
- **Repository Pattern**: All DB access must go through repository classes; never use `db.session` directly in routes.
- **Domain Events**: Any state change (Create/Update/Delete) must emit a corresponding event (e.g., `OrderCreated`).
- **Config as Code**: All environment-specific config is loaded from `settings.py` using Pydantic `BaseSettings`.
- **Soft Deletes**: Database tables use `is_deleted` boolean; never `DELETE` rows.

## Learnings
- **gRPC Timeouts**: Default timeouts are too short for complex aggregations. Set to 5s for internal calls.
- **Connection Pooling**: SQLAlchemy pool size must match max concurrent gRPC workers to avoid bottlenecks.

## Issues
- **Resolved**: `inventory` service race condition during high-concurrency stock checks.
  - *Fix*: Implemented `SELECT ... FOR UPDATE` row locking.
- **Resolved**: Memory leak in PDF generation for invoices.
  - *Fix*: Switched to streaming response instead of loading full PDF into RAM.
- **Pending**: Retry logic for RabbitMQ connection loss is flaky.

## Recent Work
### Session [inventory] [testing] - 2023-11-20 14:00
#### Goal
Implement stock reservation timeout logic

#### Summary
[inventory] Added background task to release reserved stock if payment is not received in 15 mins.
[testing] Added integration test simulating payment timeout.

#### Decisions Made
- Use Redis keys with TTL for reservation tracking (faster than DB).

### Session [gateway] [auth] - 2023-11-19 09:30
#### Goal
Rotate public keys for JWT verification

#### Summary
[gateway] Added endpoint to fetch current public keys from Auth service.
[auth] Implemented key rotation cron job.

### Session [orders] - 2023-11-18 16:15
#### Goal
Refactor order creation validation

#### Summary
[orders] Moved validation logic from `routes.py` to `services.py` to adhere to hexagonal architecture.

#### Problems Solved
- Fixed circular import between models and schemas.

### Session [infra] - 2023-11-17 11:00
#### Goal
Update Docker base images

#### Summary
[infra] Bumped python base image to 3.11-slim. Updated CI pipeline to run linter on 3.11.

### Session [docs] - 2023-11-16 13:45
#### Goal
Update API documentation

#### Summary
[docs] Added docstrings to all `OrderService` methods. Generated updated Swagger UI.
