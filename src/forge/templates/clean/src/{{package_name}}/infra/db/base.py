from __future__ import annotations
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Base(DeclarativeBase):
    pass

_engine = None
_SessionLocal = None

def init_engine(url: str):
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(url, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine, _SessionLocal