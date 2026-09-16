# CiviConnect — Guía de Laboratorio 4 (Sesiones 7 y 8)

Plataforma web de participación ciudadana y gestión de incidencias comunitarias.
Universidad Manuela Beltrán — Ingeniería de Software — Taller de Programación 2026-262.

## Arquitectura multicapa

UI  ->  NEGOCIO (app/services)  ->  ORM (app/models + app/repositories)  ->  BD (SQLite/PostgreSQL)

## Ejecución

```bash
pip install -r requirements.txt
alembic upgrade head        # aplica las 2 migraciones
pytest tests/ -v --cov=app  # 3 pruebas de integración
python demo_multicapa.py    # demo del sistema integrado
```

## Entregables de la guía

| Criterio | Evidencia |
|---|---|
| >=5 entidades ORM | 9 entidades en `app/models/entities.py` |
| >=3 repositorios CRUD | 8 repositorios en `app/repositories/` |
| Query JOIN contra N+1 | `listar_con_autor_y_categoria()`, `ranking_por_votos()` |
| >=2 migraciones | `migrations/versions/` |
| 3 pruebas de integración | `tests/test_integracion.py` |
| Pipeline CI/CD | `.github/workflows/ci.yml` |
