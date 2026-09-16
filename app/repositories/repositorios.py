"""Repositorios concretos de CiviConnect.

Cada repositorio hereda el CRUD genérico de BaseRepository y añade únicamente
las consultas propias de su agregado. Las consultas marcadas como "resuelve
N+1" usan JOIN explícito o carga ansiosa (selectinload / joinedload) para
evitar la emisión de una consulta adicional por cada fila recuperada.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.entities import (
    Auditoria,
    Categoria,
    Comentario,
    EstadoPropuesta,
    EstadoReporte,
    HistorialEstado,
    Notificacion,
    Propuesta,
    Reporte,
    RolUsuario,
    Usuario,
    Voto,
)
from app.repositories.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Usuario)

    def buscar_por_correo(self, correo: str) -> Optional[Usuario]:
        sentencia = select(Usuario).where(Usuario.correo == correo.strip().lower())
        return self.session.execute(sentencia).scalar_one_or_none()

    def listar_por_rol(self, rol: RolUsuario) -> Sequence[Usuario]:
        sentencia = select(Usuario).where(Usuario.rol == rol, Usuario.activo.is_(True))
        return self.session.execute(sentencia).scalars().all()

    def cambiar_estado_activo(self, usuario_id: int, activo: bool) -> Optional[Usuario]:
        return self.actualizar(usuario_id, activo=activo)


class PropuestaRepository(BaseRepository[Propuesta]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Propuesta)

    def listar_con_autor_y_categoria(
        self, estado: Optional[EstadoPropuesta] = None
    ) -> Sequence[Propuesta]:
        """Resuelve N+1: una sola consulta trae propuesta, autor y categoría.

        Sin joinedload, iterar `p.autor.nombre` sobre N propuestas dispararía
        N consultas adicionales (problema N+1). Con JOIN todo llega en 1 query.
        """
        sentencia = (
            select(Propuesta)
            .options(
                joinedload(Propuesta.autor),
                joinedload(Propuesta.categoria),
            )
            .order_by(Propuesta.fecha_creacion.desc())
        )
        if estado is not None:
            sentencia = sentencia.where(Propuesta.estado == estado)
        return self.session.execute(sentencia).unique().scalars().all()

    def ranking_por_votos(self, limite: int = 10) -> List[Tuple[Propuesta, int]]:
        """Resuelve N+1: agrega el conteo de votos con JOIN + GROUP BY.

        La alternativa ingenua (`len(p.votos)` por cada propuesta) ejecuta una
        consulta por fila. Aquí el motor devuelve el conteo en la misma query.
        """
        sentencia = (
            select(Propuesta, func.count(Voto.id).label("total"))
            .outerjoin(Voto, Voto.propuesta_id == Propuesta.id)
            .options(joinedload(Propuesta.categoria))
            .group_by(Propuesta.id)
            .order_by(func.count(Voto.id).desc())
            .limit(limite)
        )
        return [(fila[0], fila[1]) for fila in self.session.execute(sentencia).unique().all()]

    def cambiar_estado(
        self, propuesta_id: int, nuevo_estado: EstadoPropuesta
    ) -> Optional[Propuesta]:
        return self.actualizar(propuesta_id, estado=nuevo_estado)


class ReporteRepository(BaseRepository[Reporte]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Reporte)

    def listar_con_historial(self, estado: Optional[EstadoReporte] = None) -> Sequence[Reporte]:
        """Resuelve N+1: carga ansiosa del historial y del ciudadano autor."""
        sentencia = (
            select(Reporte)
            .options(
                selectinload(Reporte.historial),
                joinedload(Reporte.ciudadano),
                joinedload(Reporte.categoria),
            )
            .order_by(Reporte.fecha_creacion.desc())
        )
        if estado is not None:
            sentencia = sentencia.where(Reporte.estado == estado)
        return self.session.execute(sentencia).unique().scalars().all()

    def registrar_cambio_estado(
        self,
        reporte_id: int,
        gestor_id: int,
        nuevo_estado: EstadoReporte,
        observacion: str = "",
    ) -> Optional[Reporte]:
        reporte = self.obtener_por_id(reporte_id)
        if reporte is None:
            return None
        registro = HistorialEstado(
            reporte_id=reporte.id,
            gestor_id=gestor_id,
            estado_anterior=reporte.estado,
            estado_nuevo=nuevo_estado,
            observacion=observacion,
            fecha=datetime.now(timezone.utc),
        )
        reporte.estado = nuevo_estado
        self.session.add(registro)
        self.session.commit()
        self.session.refresh(reporte)
        return reporte

    def conteo_por_estado(self) -> dict[str, int]:
        """Métrica del panel estadístico, resuelta en una sola consulta."""
        sentencia = select(Reporte.estado, func.count(Reporte.id)).group_by(Reporte.estado)
        return {estado.value: total for estado, total in self.session.execute(sentencia).all()}


class VotoRepository(BaseRepository[Voto]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Voto)

    def existe_voto(self, usuario_id: int, propuesta_id: int) -> bool:
        sentencia = select(func.count(Voto.id)).where(
            Voto.usuario_id == usuario_id, Voto.propuesta_id == propuesta_id
        )
        return self.session.execute(sentencia).scalar_one() > 0

    def retirar_voto(self, usuario_id: int, propuesta_id: int) -> bool:
        sentencia = select(Voto).where(
            Voto.usuario_id == usuario_id, Voto.propuesta_id == propuesta_id
        )
        voto = self.session.execute(sentencia).scalar_one_or_none()
        if voto is None:
            return False
        self.session.delete(voto)
        self.session.commit()
        return True


class ComentarioRepository(BaseRepository[Comentario]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Comentario)

    def listar_por_propuesta(self, propuesta_id: int) -> Sequence[Comentario]:
        """Resuelve N+1: JOIN con usuarios para mostrar el nombre del autor."""
        sentencia = (
            select(Comentario)
            .join(Usuario, Usuario.id == Comentario.usuario_id)
            .options(joinedload(Comentario.autor))
            .where(Comentario.propuesta_id == propuesta_id, Comentario.moderado.is_(False))
            .order_by(Comentario.fecha_creacion)
        )
        return self.session.execute(sentencia).unique().scalars().all()

    def moderar(self, comentario_id: int) -> Optional[Comentario]:
        return self.actualizar(comentario_id, moderado=True)


class CategoriaRepository(BaseRepository[Categoria]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Categoria)


class NotificacionRepository(BaseRepository[Notificacion]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Notificacion)

    def no_leidas(self, usuario_id: int) -> Sequence[Notificacion]:
        sentencia = select(Notificacion).where(
            Notificacion.usuario_id == usuario_id, Notificacion.leido.is_(False)
        )
        return self.session.execute(sentencia).scalars().all()


class AuditoriaRepository(BaseRepository[Auditoria]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Auditoria)

    def registrar(self, usuario_id: int, accion: str, entidad: str, entidad_id: int | None = None):
        return self.crear(
            usuario_id=usuario_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            fecha=datetime.now(timezone.utc),
        )
