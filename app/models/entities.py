"""Entidades del dominio CiviConnect mapeadas con SQLAlchemy 2.0.

Nueve entidades derivadas del Modelo Entidad-Relación del proyecto:
Usuario, Categoria, Propuesta, Voto, Comentario, Reporte, HistorialEstado,
Notificacion y Auditoria.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base, TimestampMixin


class RolUsuario(str, enum.Enum):
    CIUDADANO = "ciudadano"
    GESTOR = "gestor"
    ADMINISTRADOR = "administrador"


class EstadoPropuesta(str, enum.Enum):
    PENDIENTE = "pendiente"
    APROBADA = "aprobada"
    RECHAZADA = "rechazada"
    EN_EJECUCION = "en_ejecucion"
    FINALIZADA = "finalizada"


class EstadoReporte(str, enum.Enum):
    PENDIENTE = "pendiente"
    REVISION = "revision"
    EN_PROCESO = "en_proceso"
    SOLUCIONADO = "solucionado"
    CERRADO = "cerrado"


class TipoCategoria(str, enum.Enum):
    PROPUESTA = "propuesta"
    REPORTE = "reporte"
    AMBOS = "ambos"


class Usuario(Base, TimestampMixin):
    """Habitante, gestor comunitario o administrador de la plataforma."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    correo: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(
        SAEnum(RolUsuario), default=RolUsuario.CIUDADANO, nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    foto: Mapped[Optional[str]] = mapped_column(String(255))

    propuestas: Mapped[List["Propuesta"]] = relationship(
        back_populates="autor", cascade="all, delete-orphan"
    )
    votos: Mapped[List["Voto"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
    comentarios: Mapped[List["Comentario"]] = relationship(
        back_populates="autor", cascade="all, delete-orphan"
    )
    reportes: Mapped[List["Reporte"]] = relationship(
        back_populates="ciudadano", cascade="all, delete-orphan"
    )
    notificaciones: Mapped[List["Notificacion"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )

    @validates("correo")
    def validar_correo(self, _key: str, valor: str) -> str:
        if "@" not in valor or "." not in valor.split("@")[-1]:
            raise ValueError(f"Correo electrónico inválido: {valor}")
        return valor.strip().lower()

    @validates("nombre")
    def validar_nombre(self, _key: str, valor: str) -> str:
        if not valor or len(valor.strip()) < 3:
            raise ValueError("El nombre debe tener al menos 3 caracteres")
        return valor.strip()

    def __repr__(self) -> str:
        return f"<Usuario {self.id} {self.correo} ({self.rol.value})>"


class Categoria(Base, TimestampMixin):
    """Clasificación temática compartida por propuestas y reportes."""

    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    tipo: Mapped[TipoCategoria] = mapped_column(
        SAEnum(TipoCategoria), default=TipoCategoria.AMBOS, nullable=False
    )

    propuestas: Mapped[List["Propuesta"]] = relationship(back_populates="categoria")
    reportes: Mapped[List["Reporte"]] = relationship(back_populates="categoria")

    def __repr__(self) -> str:
        return f"<Categoria {self.id} {self.nombre}>"


class Propuesta(Base, TimestampMixin):
    """Iniciativa comunitaria publicada por un ciudadano."""

    __tablename__ = "propuestas"
    __table_args__ = (Index("ix_propuestas_estado_categoria", "estado", "categoria_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    imagen: Mapped[Optional[str]] = mapped_column(String(255))
    estado: Mapped[EstadoPropuesta] = mapped_column(
        SAEnum(EstadoPropuesta), default=EstadoPropuesta.PENDIENTE, nullable=False
    )

    autor: Mapped["Usuario"] = relationship(back_populates="propuestas")
    categoria: Mapped["Categoria"] = relationship(back_populates="propuestas")
    votos: Mapped[List["Voto"]] = relationship(
        back_populates="propuesta", cascade="all, delete-orphan"
    )
    comentarios: Mapped[List["Comentario"]] = relationship(
        back_populates="propuesta", cascade="all, delete-orphan"
    )

    @validates("titulo")
    def validar_titulo(self, _key: str, valor: str) -> str:
        if not valor or len(valor.strip()) < 10:
            raise ValueError("El título debe tener al menos 10 caracteres")
        return valor.strip()

    @property
    def total_votos(self) -> int:
        return len(self.votos)

    def __repr__(self) -> str:
        return f"<Propuesta {self.id} '{self.titulo[:25]}' {self.estado.value}>"


class Voto(Base, TimestampMixin):
    """Voto único de un usuario sobre una propuesta (retirable)."""

    __tablename__ = "votos"
    __table_args__ = (
        UniqueConstraint("usuario_id", "propuesta_id", name="uq_voto_usuario_propuesta"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    propuesta_id: Mapped[int] = mapped_column(ForeignKey("propuestas.id"), nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="votos")
    propuesta: Mapped["Propuesta"] = relationship(back_populates="votos")

    def __repr__(self) -> str:
        return f"<Voto u={self.usuario_id} p={self.propuesta_id}>"


class Comentario(Base, TimestampMixin):
    """Comentario ciudadano asociado a una propuesta, sujeto a moderación."""

    __tablename__ = "comentarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    propuesta_id: Mapped[int] = mapped_column(ForeignKey("propuestas.id"), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    moderado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    autor: Mapped["Usuario"] = relationship(back_populates="comentarios")
    propuesta: Mapped["Propuesta"] = relationship(back_populates="comentarios")

    @validates("contenido")
    def validar_contenido(self, _key: str, valor: str) -> str:
        if not valor or not valor.strip():
            raise ValueError("El comentario no puede estar vacío")
        return valor.strip()


class Reporte(Base, TimestampMixin):
    """Incidencia comunitaria geolocalizada reportada por un ciudadano."""

    __tablename__ = "reportes"
    __table_args__ = (
        CheckConstraint("latitud BETWEEN -90 AND 90", name="ck_reporte_latitud"),
        CheckConstraint("longitud BETWEEN -180 AND 180", name="ck_reporte_longitud"),
        Index("ix_reportes_estado", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categorias.id"), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    latitud: Mapped[float] = mapped_column(Float, nullable=False)
    longitud: Mapped[float] = mapped_column(Float, nullable=False)
    imagen: Mapped[Optional[str]] = mapped_column(String(255))
    estado: Mapped[EstadoReporte] = mapped_column(
        SAEnum(EstadoReporte), default=EstadoReporte.PENDIENTE, nullable=False
    )
    calificacion_atencion: Mapped[Optional[int]] = mapped_column()

    ciudadano: Mapped["Usuario"] = relationship(back_populates="reportes")
    categoria: Mapped["Categoria"] = relationship(back_populates="reportes")
    historial: Mapped[List["HistorialEstado"]] = relationship(
        back_populates="reporte", cascade="all, delete-orphan", order_by="HistorialEstado.id"
    )

    @validates("latitud")
    def validar_latitud(self, _key: str, valor: float) -> float:
        if not -90 <= valor <= 90:
            raise ValueError("Latitud fuera de rango (-90 a 90)")
        return valor

    @validates("longitud")
    def validar_longitud(self, _key: str, valor: float) -> float:
        if not -180 <= valor <= 180:
            raise ValueError("Longitud fuera de rango (-180 a 180)")
        return valor

    def __repr__(self) -> str:
        return f"<Reporte {self.id} {self.estado.value}>"


class HistorialEstado(Base):
    """Trazabilidad de cada cambio de estado sobre un reporte."""

    __tablename__ = "historial_estados"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporte_id: Mapped[int] = mapped_column(ForeignKey("reportes.id"), nullable=False)
    gestor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    estado_anterior: Mapped[EstadoReporte] = mapped_column(SAEnum(EstadoReporte), nullable=False)
    estado_nuevo: Mapped[EstadoReporte] = mapped_column(SAEnum(EstadoReporte), nullable=False)
    observacion: Mapped[Optional[str]] = mapped_column(Text)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    reporte: Mapped["Reporte"] = relationship(back_populates="historial")
    gestor: Mapped["Usuario"] = relationship()


class Notificacion(Base, TimestampMixin):
    """Alerta interna generada ante cambios de estado o comentarios."""

    __tablename__ = "notificaciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(255), nullable=False)
    leido: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    usuario: Mapped["Usuario"] = relationship(back_populates="notificaciones")


class Auditoria(Base):
    """Registro inmutable de acciones sensibles del sistema."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    accion: Mapped[str] = mapped_column(String(150), nullable=False)
    entidad: Mapped[str] = mapped_column(String(60), nullable=False)
    entidad_id: Mapped[Optional[int]] = mapped_column()
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    usuario: Mapped["Usuario"] = relationship()
