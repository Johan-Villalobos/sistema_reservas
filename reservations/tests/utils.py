"""Utilidades compartidas por las pruebas de reservas."""

from datetime import time, timedelta

from django.utils import timezone

from accounts.roles import Rol
from accounts.tests.utils import crear_usuario
from reservations.models import EstadoReserva, HistorialReserva, Reserva
from spaces.tests.utils import crear_espacio

__all__ = [
    "crear_espacio",
    "crear_historial",
    "crear_reserva",
    "crear_reserva_aprobada",
    "crear_reserva_en_estado",
    "crear_usuario",
    "crear_usuario_por_rol",
    "datos_solicitud",
    "fecha_futura",
    "fecha_pasada",
]


def fecha_futura(dias=2):
    """Fecha local relativa en el futuro, sin depender de la hora exacta."""
    return timezone.localdate() + timedelta(days=dias)


def fecha_pasada(dias=2):
    """Fecha local relativa en el pasado, sin depender de la hora exacta."""
    return timezone.localdate() - timedelta(days=dias)


def datos_solicitud(**cambios):
    """Datos válidos de solicitud con fecha de mañana y franja 10:00-11:00."""
    datos = {
        "fecha": fecha_futura(1),
        "hora_inicio": time(10, 0),
        "hora_fin": time(11, 0),
        "motivo": "Reserva de prueba",
    }
    datos.update(cambios)
    return datos


def crear_usuario_por_rol(rol=Rol.SOLICITANTE, **datos):
    """Crea un usuario de prueba con el rol indicado."""
    return crear_usuario(rol=rol, **datos)


def crear_reserva(
    *,
    espacio,
    solicitante=None,
    estado=EstadoReserva.PENDIENTE,
    **cambios,
):
    """Crea una reserva directamente por ORM para preparar escenarios.

    Se usa cuando la prueba necesita un estado distinto de ``PENDIENTE`` o una
    reserva que sería rechazada por la validación de disponibilidad al crearse.
    No registra historial: las pruebas que lo necesiten usan
    ``crear_historial`` o un servicio.
    """
    datos = datos_solicitud(**cambios)
    if solicitante is None:
        solicitante = crear_usuario()
    return Reserva.objects.create(
        espacio=espacio,
        solicitante=solicitante,
        estado=estado,
        **datos,
    )


def crear_reserva_aprobada(*, espacio, **cambios):
    """Crea una reserva ``APROBADA`` con franja 10:00-12:00 por defecto."""
    cambios.setdefault("hora_inicio", time(10, 0))
    cambios.setdefault("hora_fin", time(12, 0))
    return crear_reserva(
        espacio=espacio,
        estado=EstadoReserva.APROBADA,
        **cambios,
    )


def crear_reserva_en_estado(estado, *, espacio, **cambios):
    """Crea una reserva en el estado indicado."""
    return crear_reserva(espacio=espacio, estado=estado, **cambios)


def crear_historial(
    *,
    reserva,
    actor,
    estado_anterior=None,
    estado_nuevo=EstadoReserva.PENDIENTE,
    observacion="",
    fecha_evento=None,
):
    """Inserta un evento de historial para preparar escenarios de consulta."""
    datos = {
        "reserva": reserva,
        "actor": actor,
        "estado_anterior": estado_anterior,
        "estado_nuevo": estado_nuevo,
        "observacion": observacion,
    }
    if fecha_evento is not None:
        datos["fecha_evento"] = fecha_evento
    return HistorialReserva.objects.create(**datos)
