# Novex

Агрегатор курьерских служб. Клиент рассчитывает тарифы нескольких перевозчиков, оформляет и оплачивает отправление, получает трек-номер и отслеживает доставку — всё в одном интерфейсе.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js · React · TypeScript |
| Backend | FastAPI · Python 3.12 · SQLAlchemy · Alembic |
| Workers | Background Python workers (Redis queue) |
| Storage | PostgreSQL · Redis · MinIO |
| Infra | Docker Compose · Nginx · Certbot (Let's Encrypt) |
| Payments | Kaspi Pay |
| Carriers | Azimuth · Exline |

## Project structure

```
novex/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── modules/      # domain modules (orders, shipments, quotes, payments, …)
│   │   └── core/         # config, auth, db session
│   ├── integrations/
│   │   └── couriers/     # carrier adapter layer (Azimuth, Exline)
│   ├── workers/          # async background tasks
│   └── migrations/       # Alembic migrations
├── frontend/             # Next.js app
├── infra/
│   ├── compose/          # docker-compose.yml / docker-compose.dev.yml
│   ├── docker/           # Dockerfiles
│   └── nginx/            # nginx config templates
└── scripts/
```

## Local dev

**Prerequisites:** Docker, Docker Compose

```bash
# 1. Copy env files and fill in the values
cp infra/env/backend.env.example infra/env/backend.env

# 2. Start all services (postgres, redis, minio, backend, worker, frontend, nginx)
docker compose -f infra/compose/docker-compose.dev.yml up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/api/v1 |
| API Docs | http://localhost:8000/docs |
| MinIO Console | http://localhost:9001 |

Migrations run automatically on startup via a one-shot `migrate` container.

## Production

```bash
docker compose -f infra/compose/docker-compose.yml up -d
```

TLS is handled by Certbot: the `certbot` container renews every 12h, nginx reloads every 6h to pick up new certs.

## Domain modules

| Module | Responsibility |
|---|---|
| `identity` | Auth, JWT, registration |
| `customers` | Customer profiles |
| `quotes` | Tariff calculation across carriers |
| `orders` | Order lifecycle |
| `shipments` | Shipment creation & dispatch |
| `tracking` | Status polling & webhooks |
| `payments` | Kaspi Pay integration |
| `documents` | Labels & invoices (PDF via fpdf2/WeasyPrint) |
| `notifications` | Email notifications |
| `reviews` | Ratings after delivery |
| `carriers` | Carrier registry & credentials |
