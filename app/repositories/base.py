"""Repositorio genérico con operaciones CRUD reutilizables.

Aplica el principio de reutilización de código exigido como requerimiento no
funcional: las cuatro operaciones básicas se implementan una sola vez y los
repositorios concretos heredan de aquí, añadiendo únicamente consultas propias
de su dominio. También respeta el principio de sustitución de Liskov (SOLID):
cualquier repositorio concreto puede usarse donde se espere un BaseRepository.
"""
from __future__ import annotations

from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """CRUD genérico sobre cualquier entidad mapeada."""

    def __init__(self, session: Session, model: Type[ModelType]) -> None:
        self.session = session
        self.model = model

    def crear(self, **datos) -> ModelType:
        instancia = self.model(**datos)
        self.session.add(instancia)
        self.session.commit()
        self.session.refresh(instancia)
        return instancia

    def obtener_por_id(self, registro_id: int) -> Optional[ModelType]:
        return self.session.get(self.model, registro_id)

    def listar(self, limite: int = 100, desplazamiento: int = 0) -> Sequence[ModelType]:
        sentencia = select(self.model).limit(limite).offset(desplazamiento)
        return self.session.execute(sentencia).scalars().all()

    def actualizar(self, registro_id: int, **cambios) -> Optional[ModelType]:
        instancia = self.obtener_por_id(registro_id)
        if instancia is None:
            return None
        for campo, valor in cambios.items():
            if hasattr(instancia, campo):
                setattr(instancia, campo, valor)
        self.session.commit()
        self.session.refresh(instancia)
        return instancia

    def eliminar(self, registro_id: int) -> bool:
        instancia = self.obtener_por_id(registro_id)
        if instancia is None:
            return False
        self.session.delete(instancia)
        self.session.commit()
        return True

    def contar(self) -> int:
        return self.session.execute(
            select(func.count()).select_from(self.model)
        ).scalar_one()
