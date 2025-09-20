# Forge CLI

**Forge** is a command-line tool to scaffold and manage **Flask projects** with **Clean Architecture** and strict **OOP boundaries**.
It removes boilerplate, enforces best practices, and provides generators for entities, repositories, services, and controllers — all wired with a minimal DI container.

---

## ✨ Features

- 🏗️ **Single canonical template**: Clean Architecture (domain/app/infra/interfaces/shared)
- 🔒 **Strict OOP**: no functional boilerplate, clear layering
- 🧩 **Generators**: add bounded contexts, entities, repos, services, controllers, tests
- 📦 **Plugins**: OpenAPI (Smorest), JWT auth, telemetry (planned)
- ⚡ **DX polish**: Ruff + Black + pre-commit, problem+json error model, request IDs, structured logs
- 🗄️ **Database support**: SQLAlchemy + Alembic migrations
- ✅ **Tests**: scaffolded per layer (domain/app/infra/http)
- 🔧 **CLI utilities**: lint, format, db, doctor, tasks (planned)

---

## 📦 Installation

### From PyPI

```bash
pipx install flask-forge-cli
# or
pip install flask-forge-cli
```

### From source (dev mode)

```bash
git clone https://github.com/<you>/flask-forge.git
cd flask-forge
pip install -e .
```

---

## 🚀 Quickstart

```bash
# create a new clean-architecture Flask project
forge new shop
cd shop

# install dev dependencies
pip install -e ".[dev]"
cp .env.example .env

# init DB
forge db init
forge db migrate -m "init"
forge db upgrade

# run dev server
forge run dev -p 8000

# open http://localhost:8000/health
```

---

## 🧩 Generators

```bash
# bounded context
forge generate bc catalog

# entity + repo interface
forge generate entity catalog Product

# repo implementation (SQLAlchemy)
forge generate repo catalog Product --impl=sqlalchemy

# service
forge generate service catalog ProductService

# controller (Flask blueprint)
forge generate controller catalog product

# full resource across layers (+ tests)
forge generate resource catalog Product
```

---

## 🔌 Plugins

```bash
forge plugin openapi   # add OpenAPI (Smorest + Marshmallow)
forge plugin jwt       # add JWT auth endpoints
forge plugin telemetry # (planned) observability hooks
```

---

## 🧑‍💻 Developer Workflow

```bash
# lint (Ruff)
forge lint

# format (Black)
forge format

# check (Ruff + Black)
forge check

# run tests
pytest -q

# check environment
forge doctor all
```

Enable pre-commit hooks:

```bash
pre-commit install
```

---

## 📂 Project Layout (generated app)

```
src/<pkg>/
  app/            # application layer (use cases / services)
  domain/         # entities, repositories, value objects
  infra/          # db, repo impls
  interfaces/     # http controllers, api, middleware
  shared/         # config, logging, DI
  main.py         # thin bootstrap
tests/            # per-layer tests
```

---

## 📜 License

MIT © Kevin Martinez
