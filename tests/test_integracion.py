"""Pruebas de integración de CiviConnect.

Cada prueba recorre la pila completa NEGOCIO -> ORM -> BD contra una base de
datos SQLite en memoria, sin mocks, de modo que se validan también las
restricciones reales del esquema (unicidad, claves foráneas, CHECK).
"""
from __future__ import annotations

import pytest
from sqlalchemy import event

from app.models.entities import EstadoPropuesta, EstadoReporte
from app.repositories.repositorios import PropuestaRepository
from app.services.servicios import (
    ReglaNegocioError,
    ServicioEstadisticas,
    ServicioIncidencias,
    ServicioParticipacion,
)


class TestIntegracionParticipacion:
    """Prueba 1 — RF05, RF07: ciclo de propuesta y voto único por usuario."""

    def test_ciclo_propuesta_y_voto_unico(self, session, ciudadano, categoria):
        participacion = ServicioParticipacion(session)

        propuesta = participacion.publicar_propuesta(
            usuario_id=ciudadano.id,
            categoria_id=categoria.id,
            titulo="Ciclovía nocturna en el parque central",
            descripcion="Habilitar la ciclovía los fines de semana en horario nocturno.",
        )
        assert propuesta.id is not None
        assert propuesta.estado == EstadoPropuesta.PENDIENTE

        # Una propuesta pendiente todavía no admite votos.
        with pytest.raises(ReglaNegocioError, match="aprobadas"):
            participacion.votar(ciudadano.id, propuesta.id)

        participacion.aprobar(propuesta.id)
        voto = participacion.votar(ciudadano.id, propuesta.id)
        assert voto.id is not None

        # RF07: el voto es único por usuario y propuesta.
        with pytest.raises(ReglaNegocioError, match="ya votó"):
            participacion.votar(ciudadano.id, propuesta.id)

        # El voto puede retirarse y volver a emitirse.
        assert participacion.retirar_voto(ciudadano.id, propuesta.id) is True
        assert participacion.votar(ciudadano.id, propuesta.id).id is not None


class TestIntegracionIncidencias:
    """Prueba 2 — RF09, RF10, RF14: seguimiento de estados con historial."""

    def test_flujo_reporte_hasta_cierre(self, session, ciudadano, gestor, categoria):
        incidencias = ServicioIncidencias(session)

        reporte = incidencias.reportar(
            usuario_id=ciudadano.id,
            categoria_id=categoria.id,
            descripcion="Luminaria apagada en la calle 12 con carrera 45.",
            latitud=4.7110,
            longitud=-74.0721,
        )
        assert reporte.estado == EstadoReporte.PENDIENTE

        # No se puede saltar estados de la máquina de estados.
        with pytest.raises(ReglaNegocioError, match="Transición inválida"):
            incidencias.avanzar_estado(reporte.id, gestor.id, EstadoReporte.SOLUCIONADO)

        for nuevo in (
            EstadoReporte.REVISION,
            EstadoReporte.EN_PROCESO,
            EstadoReporte.SOLUCIONADO,
            EstadoReporte.CERRADO,
        ):
            incidencias.avanzar_estado(reporte.id, gestor.id, nuevo, f"Cambio a {nuevo.value}")

        session.refresh(reporte)
        assert reporte.estado == EstadoReporte.CERRADO
        assert len(reporte.historial) == 4
        assert reporte.historial[0].estado_anterior == EstadoReporte.PENDIENTE

        # RF14: cada cambio de estado generó una notificación al ciudadano.
        assert len(incidencias.notificaciones.no_leidas(ciudadano.id)) == 4

        # RF11: la evaluación de atención ya es válida sobre un reporte cerrado.
        evaluado = incidencias.evaluar_atencion(reporte.id, 5)
        assert evaluado.calificacion_atencion == 5


class TestIntegracionConsultasYEstadisticas:
    """Prueba 3 — RF06, RF15: la consulta con JOIN evita el problema N+1."""

    def test_listado_con_join_no_genera_consultas_extra(
        self, session, engine, ciudadano, categoria
    ):
        participacion = ServicioParticipacion(session)
        for indice in range(5):
            propuesta = participacion.publicar_propuesta(
                usuario_id=ciudadano.id,
                categoria_id=categoria.id,
                titulo=f"Propuesta comunitaria número {indice}",
                descripcion="Descripción de prueba para el listado con JOIN.",
            )
            participacion.aprobar(propuesta.id)

        session.expire_all()
        consultas: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def contar(_conn, _cursor, sentencia, *_args):
            if sentencia.strip().upper().startswith("SELECT"):
                consultas.append(sentencia)

        repositorio = PropuestaRepository(session)
        propuestas = repositorio.listar_con_autor_y_categoria(EstadoPropuesta.APROBADA)
        # Acceder a las relaciones NO debe disparar consultas adicionales.
        nombres = [f"{p.autor.nombre} - {p.categoria.nombre}" for p in propuestas]

        event.remove(engine, "before_cursor_execute", contar)

        assert len(propuestas) == 5
        assert len(nombres) == 5
        assert len(consultas) == 1, (
            f"Se esperaba 1 consulta con JOIN, se ejecutaron {len(consultas)} (problema N+1)"
        )

        # RF15: el resumen estadístico refleja los datos persistidos.
        resumen = ServicioEstadisticas(session).resumen()
        assert resumen["total_propuestas"] == 5
        assert resumen["total_usuarios"] == 1
