"""Fixtures compartidas: base de datos SQLite en memoria para CI/CD."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.entities import Categoria, RolUsuario, TipoCategoria
from app.services.servicios import ServicioAutenticacion


@pytest.fixture()
def engine():
    """Motor SQLite en memoria: sin dependencia de un servidor externo."""
    motor = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(motor, "connect")
    def activar_claves_foraneas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(motor)
    yield motor
    Base.metadata.drop_all(motor)
    motor.dispose()


@pytest.fixture()
def session(engine):
    Sesion = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    sesion = Sesion()
    yield sesion
    sesion.close()


@pytest.fixture()
def categoria(session) -> Categoria:
    cat = Categoria(nombre="Infraestructura", tipo=TipoCategoria.AMBOS)
    session.add(cat)
    session.commit()
    return cat


@pytest.fixture()
def ciudadano(session):
    auth = ServicioAutenticacion(session)
    return auth.registrar("Laura Méndez", "laura@correo.com", "Clave12345")


@pytest.fixture()
def gestor(session):
    auth = ServicioAutenticacion(session)
    return auth.registrar(
        "Carlos Gutiérrez", "carlos@correo.com", "Clave12345", RolUsuario.GESTOR
    )
