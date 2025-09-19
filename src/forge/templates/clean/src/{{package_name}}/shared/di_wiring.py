from __future__ import annotations
from .di import Container
from ..shared.config import Settings
from ..infra.db.base import init_engine

# Core providers (db/session, etc.)

def register_core(container: Container, settings: Settings) -> None:
    engine, SessionLocal = init_engine(settings.database_url)
    container.register("db.session_factory", lambda: SessionLocal, singleton=True)

# Feature providers (extend as you generate resources)

def register_features(container: Container) -> None:
    # Generators append feature registrations here (idempotent)
    pass