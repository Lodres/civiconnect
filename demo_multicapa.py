"""Demo del sistema multicapa CiviConnect: UI -> NEGOCIO -> ORM -> BD.

Ejecuta un recorrido completo por las cuatro capas y mide, sobre la misma
base de datos, el número de consultas SQL emitidas por la versión ingenua
(problema N+1) frente a la versión con JOIN / carga ansiosa.
"""
from __future__ import annotations

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.entities import Categoria, EstadoPropuesta, EstadoReporte, Propuesta, TipoCategoria
from app.repositories.repositorios import PropuestaRepository
from app.services.servicios import (
    ServicioAutenticacion,
    ServicioEstadisticas,
    ServicioIncidencias,
    ServicioParticipacion,
)

CONSULTAS: list[str] = []


def preparar_motor():
    motor = create_engine("sqlite+pysqlite:///:memory:", future=True)

    @event.listens_for(motor, "before_cursor_execute")
    def registrar(_conn, _cursor, sentencia, *_args):
        if sentencia.strip().upper().startswith("SELECT"):
            CONSULTAS.append(sentencia)

    Base.metadata.create_all(motor)
    return motor


def titulo(texto: str) -> None:
    print(f"\n{'=' * 68}\n  {texto}\n{'=' * 68}")


def main() -> None:
    motor = preparar_motor()
    session = sessionmaker(bind=motor, expire_on_commit=False, future=True)()

    titulo("CAPA 1 - UI  (simulada por consola)")
    print("  Pantallas: login, dashboard ciudadano, reporte de incidencia, panel admin")

    titulo("CAPA 2 - NEGOCIO  (servicios con reglas de dominio)")
    auth = ServicioAutenticacion(session)
    participacion = ServicioParticipacion(session)
    incidencias = ServicioIncidencias(session)

    nombres_categorias = [
        "Infraestructura",
        "Servicios públicos",
        "Seguridad",
        "Convivencia",
        "Medio ambiente",
    ]
    categorias = [Categoria(nombre=n, tipo=TipoCategoria.AMBOS) for n in nombres_categorias]
    session.add_all(categorias)
    session.commit()
    categoria = categorias[0]

    from app.models.entities import RolUsuario

    laura = auth.registrar("Laura Méndez", "laura@correo.com", "Clave12345")
    carlos = auth.registrar("Carlos Gutiérrez", "carlos@correo.com", "Clave12345", RolUsuario.GESTOR)
    print(f"  Usuario registrado : {laura.nombre} ({laura.rol.value})")
    print(f"  Usuario registrado : {carlos.nombre} ({carlos.rol.value})")
    print(f"  Autenticación      : {auth.autenticar('laura@correo.com', 'Clave12345').correo} OK")

    titulo("CAPA 3 - ORM  (SQLAlchemy 2.0: entidades y repositorios)")
    # 20 vecinos distintos publican una propuesta cada uno: así cada fila del
    # listado apunta a un autor y una categoría diferentes, que es el escenario
    # donde el problema N+1 realmente se manifiesta.
    vecinos = [
        auth.registrar(f"Vecino Número {i:02d}", f"vecino{i:02d}@correo.com", "Clave12345")
        for i in range(1, 21)
    ]
    for indice, vecino in enumerate(vecinos, start=1):
        propuesta = participacion.publicar_propuesta(
            usuario_id=vecino.id,
            categoria_id=categorias[indice % len(categorias)].id,
            titulo=f"Mejora comunitaria número {indice:02d}",
            descripcion="Propuesta generada para la demostración de la capa ORM.",
        )
        participacion.aprobar(propuesta.id)
        participacion.votar(vecino.id, propuesta.id)
    print(f"  Usuarios persistidos  : {auth.usuarios.contar()}")
    print(f"  Propuestas persistidas: {participacion.propuestas.contar()}")

    reporte = incidencias.reportar(
        usuario_id=laura.id,
        categoria_id=categoria.id,
        descripcion="Luminaria apagada en la calle 12 con carrera 45.",
        latitud=4.7110,
        longitud=-74.0721,
    )
    for nuevo in (EstadoReporte.REVISION, EstadoReporte.EN_PROCESO, EstadoReporte.SOLUCIONADO):
        incidencias.avanzar_estado(reporte.id, carlos.id, nuevo, f"Cambio a {nuevo.value}")
    session.refresh(reporte)
    print(f"  Reporte #{reporte.id} estado final: {reporte.estado.value}")
    print(f"  Registros de historial (trazabilidad): {len(reporte.historial)}")

    titulo("CAPA 4 - BD  (medición del problema N+1)")
    repositorio = PropuestaRepository(session)

    session.expire_all()
    CONSULTAS.clear()
    propuestas = session.execute(select(Propuesta).where(Propuesta.estado == EstadoPropuesta.APROBADA)).scalars().all()
    _ = [f"{p.autor.nombre}-{p.categoria.nombre}" for p in propuestas]
    consultas_ingenuas = len(CONSULTAS)

    session.expire_all()
    CONSULTAS.clear()
    propuestas = repositorio.listar_con_autor_y_categoria(EstadoPropuesta.APROBADA)
    _ = [f"{p.autor.nombre}-{p.categoria.nombre}" for p in propuestas]
    consultas_optimizadas = len(CONSULTAS)

    print(f"  Filas recuperadas                     : {len(propuestas)}")
    print(f"  Consultas SIN JOIN (problema N+1)     : {consultas_ingenuas}")
    print(f"  Consultas CON JOIN (joinedload)       : {consultas_optimizadas}")
    reduccion = 100 * (1 - consultas_optimizadas / consultas_ingenuas)
    print(f"  Reducción de consultas                : {reduccion:.1f} %")

    titulo("PANEL ESTADÍSTICO (RF15)")
    for clave, valor in ServicioEstadisticas(session).resumen().items():
        print(f"  {clave:22s}: {valor}")

    print("\n  Top 3 propuestas por votos:")
    for propuesta, total in participacion.ranking(3):
        print(f"    - {propuesta.titulo:38s} {total} voto(s)")

    session.close()


if __name__ == "__main__":
    main()
