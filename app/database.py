"""Configuración central del ORM (SQLAlchemy 2.0) para CiviConnect."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    """Marca de tiempo en UTC. Reutilizada por todas las entidades."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base declarativa común a todas las entidades del dominio."""


class TimestampMixin:
    """Mixin reutilizable: audita creación y actualización de cada registro.

    Cumple el requerimiento no funcional de reutilización de código: en lugar de
    repetir dos columnas en nueve entidades, se declaran una sola vez.
    """

    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///civiconnect.db")

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_session():
    """Generador de sesiones para la capa de servicios."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
