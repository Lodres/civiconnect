"""semilla de categorias base

Revision ID: 72ce7c4a0209
Revises: 8d1dfaa877b7
Create Date: 2026-09-15 19:49:02.976853

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision: str = '72ce7c4a0209'
down_revision: Union[str, Sequence[str], None] = '8d1dfaa877b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CATEGORIAS_BASE = [
    ("Infraestructura", "ambos"),
    ("Servicios públicos", "ambos"),
    ("Seguridad", "ambos"),
    ("Convivencia", "reporte"),
    ("Medio ambiente", "propuesta"),
    ("Cultura y deporte", "propuesta"),
]


def upgrade() -> None:
    """Inserta el catálogo mínimo de categorías requerido por el MVP."""
    tabla_categorias = sa.table(
        "categorias",
        sa.column("nombre", sa.String),
        sa.column("tipo", sa.String),
        sa.column("fecha_creacion", sa.DateTime),
        sa.column("fecha_actualizacion", sa.DateTime),
    )
    ahora = datetime.now(timezone.utc)
    op.bulk_insert(
        tabla_categorias,
        [
            {
                "nombre": nombre,
                "tipo": tipo,
                "fecha_creacion": ahora,
                "fecha_actualizacion": ahora,
            }
            for nombre, tipo in CATEGORIAS_BASE
        ],
    )


def downgrade() -> None:
    """Elimina únicamente las categorías sembradas por esta migración."""
    nombres = ", ".join(f"'{nombre}'" for nombre, _ in CATEGORIAS_BASE)
    op.execute(f"DELETE FROM categorias WHERE nombre IN ({nombres})")
