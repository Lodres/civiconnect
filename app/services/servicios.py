"""Capa de negocio de CiviConnect (UI -> NEGOCIO -> ORM -> BD).

Los servicios contienen las reglas del dominio y no conocen detalles de
persistencia: delegan todo acceso a datos en los repositorios. Esto cumple el
principio de inversión de dependencias (SOLID) y permite probar la lógica con
una base de datos en memoria.
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import bcrypt
from sqlalchemy.orm import Session

from app.models.entities import (
    EstadoPropuesta,
    EstadoReporte,
    Propuesta,
    Reporte,
    RolUsuario,
    Usuario,
)
from app.repositories.repositorios import (
    AuditoriaRepository,
    ComentarioRepository,
    NotificacionRepository,
    PropuestaRepository,
    ReporteRepository,
    UsuarioRepository,
    VotoRepository,
)


class ReglaNegocioError(Exception):
    """Violación de una regla de negocio del dominio."""


class ServicioAutenticacion:
    """RF01-RF04: registro, autenticación y gestión de perfil."""

    def __init__(self, session: Session) -> None:
        self.usuarios = UsuarioRepository(session)
        self.auditoria = AuditoriaRepository(session)

    @staticmethod
    def _hashear(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _verificar(password: str, hash_guardado: str) -> bool:
        return bcrypt.checkpw(password.encode(), hash_guardado.encode())

    def registrar(
        self, nombre: str, correo: str, password: str, rol: RolUsuario = RolUsuario.CIUDADANO
    ) -> Usuario:
        if len(password) < 8:
            raise ReglaNegocioError("La contraseña debe tener al menos 8 caracteres")
        if self.usuarios.buscar_por_correo(correo):
            raise ReglaNegocioError(f"El correo {correo} ya está registrado")
        return self.usuarios.crear(
            nombre=nombre, correo=correo, password_hash=self._hashear(password), rol=rol
        )

    def autenticar(self, correo: str, password: str) -> Usuario:
        usuario = self.usuarios.buscar_por_correo(correo)
        if usuario is None or not self._verificar(password, usuario.password_hash):
            raise ReglaNegocioError("Credenciales inválidas")
        if not usuario.activo:
            raise ReglaNegocioError("La cuenta se encuentra desactivada")
        return usuario


class ServicioParticipacion:
    """RF05-RF08, RF12: propuestas, votación y comentarios."""

    def __init__(self, session: Session) -> None:
        self.propuestas = PropuestaRepository(session)
        self.votos = VotoRepository(session)
        self.comentarios = ComentarioRepository(session)
        self.notificaciones = NotificacionRepository(session)

    def publicar_propuesta(
        self, usuario_id: int, categoria_id: int, titulo: str, descripcion: str
    ) -> Propuesta:
        return self.propuestas.crear(
            usuario_id=usuario_id,
            categoria_id=categoria_id,
            titulo=titulo,
            descripcion=descripcion,
            estado=EstadoPropuesta.PENDIENTE,
        )

    def votar(self, usuario_id: int, propuesta_id: int):
        """RF07: el voto es único por usuario y propuesta."""
        propuesta = self.propuestas.obtener_por_id(propuesta_id)
        if propuesta is None:
            raise ReglaNegocioError("La propuesta no existe")
        if propuesta.estado != EstadoPropuesta.APROBADA:
            raise ReglaNegocioError("Solo se pueden votar propuestas aprobadas")
        if self.votos.existe_voto(usuario_id, propuesta_id):
            raise ReglaNegocioError("El usuario ya votó esta propuesta")
        return self.votos.crear(usuario_id=usuario_id, propuesta_id=propuesta_id)

    def retirar_voto(self, usuario_id: int, propuesta_id: int) -> bool:
        return self.votos.retirar_voto(usuario_id, propuesta_id)

    def aprobar(self, propuesta_id: int) -> Optional[Propuesta]:
        return self.propuestas.cambiar_estado(propuesta_id, EstadoPropuesta.APROBADA)

    def rechazar(self, propuesta_id: int) -> Optional[Propuesta]:
        return self.propuestas.cambiar_estado(propuesta_id, EstadoPropuesta.RECHAZADA)

    def listar_aprobadas(self) -> Sequence[Propuesta]:
        return self.propuestas.listar_con_autor_y_categoria(EstadoPropuesta.APROBADA)

    def ranking(self, limite: int = 5) -> List[Tuple[Propuesta, int]]:
        return self.propuestas.ranking_por_votos(limite)


class ServicioIncidencias:
    """RF09-RF11, RF14: reporte, seguimiento y notificación de incidencias."""

    TRANSICIONES_VALIDAS = {
        EstadoReporte.PENDIENTE: {EstadoReporte.REVISION},
        EstadoReporte.REVISION: {EstadoReporte.EN_PROCESO, EstadoReporte.PENDIENTE},
        EstadoReporte.EN_PROCESO: {EstadoReporte.SOLUCIONADO},
        EstadoReporte.SOLUCIONADO: {EstadoReporte.CERRADO},
        EstadoReporte.CERRADO: set(),
    }

    def __init__(self, session: Session) -> None:
        self.reportes = ReporteRepository(session)
        self.notificaciones = NotificacionRepository(session)

    def reportar(
        self,
        usuario_id: int,
        categoria_id: int,
        descripcion: str,
        latitud: float,
        longitud: float,
    ) -> Reporte:
        return self.reportes.crear(
            usuario_id=usuario_id,
            categoria_id=categoria_id,
            descripcion=descripcion,
            latitud=latitud,
            longitud=longitud,
            estado=EstadoReporte.PENDIENTE,
        )

    def avanzar_estado(
        self, reporte_id: int, gestor_id: int, nuevo_estado: EstadoReporte, observacion: str = ""
    ) -> Reporte:
        """RF10: valida la máquina de estados antes de persistir el cambio."""
        reporte = self.reportes.obtener_por_id(reporte_id)
        if reporte is None:
            raise ReglaNegocioError("El reporte no existe")
        permitidos = self.TRANSICIONES_VALIDAS[reporte.estado]
        if nuevo_estado not in permitidos:
            raise ReglaNegocioError(
                f"Transición inválida: {reporte.estado.value} -> {nuevo_estado.value}"
            )
        actualizado = self.reportes.registrar_cambio_estado(
            reporte_id, gestor_id, nuevo_estado, observacion
        )
        self.notificaciones.crear(
            usuario_id=actualizado.usuario_id,
            mensaje=f"Tu reporte #{reporte_id} cambió a '{nuevo_estado.value}'",
        )
        return actualizado

    def evaluar_atencion(self, reporte_id: int, calificacion: int) -> Reporte:
        """RF11: la evaluación solo aplica a reportes solucionados o cerrados."""
        if not 1 <= calificacion <= 5:
            raise ReglaNegocioError("La calificación debe estar entre 1 y 5")
        reporte = self.reportes.obtener_por_id(reporte_id)
        if reporte is None:
            raise ReglaNegocioError("El reporte no existe")
        if reporte.estado not in (EstadoReporte.SOLUCIONADO, EstadoReporte.CERRADO):
            raise ReglaNegocioError("Solo se evalúan reportes solucionados o cerrados")
        return self.reportes.actualizar(reporte_id, calificacion_atencion=calificacion)


class ServicioEstadisticas:
    """RF15: panel estadístico y métricas de participación."""

    def __init__(self, session: Session) -> None:
        self.propuestas = PropuestaRepository(session)
        self.reportes = ReporteRepository(session)
        self.usuarios = UsuarioRepository(session)
        self.votos = VotoRepository(session)

    def resumen(self) -> dict[str, object]:
        return {
            "total_usuarios": self.usuarios.contar(),
            "total_propuestas": self.propuestas.contar(),
            "total_reportes": self.reportes.contar(),
            "total_votos": self.votos.contar(),
            "reportes_por_estado": self.reportes.conteo_por_estado(),
        }
