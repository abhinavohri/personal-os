# PageCraft

PageCraft is an interactive, progression-based course for learning database internals from disk pages through distributed systems.

## Run locally

```bash
docker compose up --build
```

Open <http://localhost:5173>. The API is available at <http://localhost:8000/docs>.

Progress is stored in PostgreSQL in the `postgres_data` Docker volume. To stop the app, run `docker compose down`. To intentionally erase all progress, run `docker compose down -v`.

## Development

The stack is React 19 + TypeScript + Vite, FastAPI + SQLAlchemy, and PostgreSQL 16. The app intentionally has no authentication yet; a stable local learner ID is stored in the browser and all progress is server-side.

```bash
docker compose up db
docker compose run --rm api pytest
docker compose run --rm web npm test
```

See [docs/PRD.md](docs/PRD.md), [docs/CURRICULUM.md](docs/CURRICULUM.md), and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
