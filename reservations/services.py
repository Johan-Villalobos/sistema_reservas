"""Reglas de negocio de las solicitudes de reserva.

Concentra la lectura del horario operativo, la validación de la franja, la
fecha, el motivo y el estado del espacio, la detección de cruces, la consulta
de franjas ocupadas y la creación y aprobación transaccionales. Las vistas y
los formularios solo traducen los errores de este módulo.
"""

from datetime import datetime, time

from django.conf import settings
from django.core.exceptions import (
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.db import connection, transaction
from django.utils import timezone

from accounts.roles import Rol
from spaces.models import EspacioAcademico

from .models import EstadoReserva, HistorialReserva, Reserva
from .permissions import puede_cancelar_reserva

MENSAJE_HORA_FIN = "La hora de fin debe ser mayor que la hora de inicio."
MENSAJE_MOTIVO_VACIO = "El motivo es obligatorio."
MENSAJE_MOTIVO_LARGO = "El motivo no puede superar los 255 caracteres."
MENSAJE_ESPACIO_INACTIVO = "El espacio seleccionado no está activo."
MENSAJE_ESPACIO_INEXISTENTE = "El espacio seleccionado no existe."
MENSAJE_INICIO_PASADO = (
    "La fecha y la hora de inicio no pueden estar en el pasado."
)
MENSAJE_SOLO_APROBAR_PENDIENTES = (
    "Solo se pueden aprobar solicitudes pendientes."
)
MENSAJE_SOLO_RECHAZAR_PENDIENTES = (
    "Solo se pueden rechazar solicitudes pendientes."
)
MENSAJE_DECISOR_REQUERIDO = (
    "Solo un aprobador o un administrador puede decidir solicitudes."
)
MENSAJE_AUTODECISION = "No puede decidir sobre su propia solicitud."
MENSAJE_YA_DECIDIDA = "La solicitud ya fue decidida por otro usuario."
MENSAJE_MOTIVO_DECISION_VACIO = "El motivo del rechazo es obligatorio."
MENSAJE_SOLO_CANCELAR_ACTIVAS = (
    "Solo se pueden cancelar reservas pendientes o aprobadas."
)
MENSAJE_CANCELACION_INICIADA = (
    "La reserva ya inició y no puede cancelarse."
)
MENSAJE_CANCELACION_CAMBIO = (
    "La reserva cambió de estado; vuelva a intentarlo."
)
MENSAJE_CANCELACION_NO_AUTORIZADA = (
    "Solo el solicitante o un administrador puede cancelar la reserva."
)

MOTIVO_YA_CANCELADA = "La reserva ya está cancelada"
MOTIVO_RECHAZADA = "La reserva fue rechazada"
MOTIVO_YA_INICIADA = "La reserva ya inició"
MOTIVO_ESTADO_NO_CANCELABLE = "El estado no permite cancelar"

TRANSICIONES_APROBACION = {
    (EstadoReserva.PENDIENTE, EstadoReserva.APROBADA),
    (EstadoReserva.PENDIENTE, EstadoReserva.RECHAZADA),
}

TRANSICIONES_CANCELACION = {
    (EstadoReserva.PENDIENTE, EstadoReserva.CANCELADA),
    (EstadoReserva.APROBADA, EstadoReserva.CANCELADA),
}

ETIQUETAS_ESTADO = {
    EstadoReserva.PENDIENTE: "pendiente",
    EstadoReserva.APROBADA: "aprobada",
    EstadoReserva.RECHAZADA: "rechazada",
    EstadoReserva.CANCELADA: "cancelada",
}


def obtener_horario_operativo():
    """Devuelve ``(apertura, cierre)`` a partir de los settings.

    Lanza ``ImproperlyConfigured`` si los valores no son horas ISO válidas o
    si la apertura no es anterior al cierre.
    """
    try:
        apertura = time.fromisoformat(settings.HORARIO_OPERATIVO_INICIO)
        cierre = time.fromisoformat(settings.HORARIO_OPERATIVO_FIN)
    except (TypeError, ValueError) as error:
        raise ImproperlyConfigured(
            "HORARIO_OPERATIVO_INICIO y HORARIO_OPERATIVO_FIN deben ser "
            "horas ISO válidas (por ejemplo, '06:00')."
        ) from error

    if apertura >= cierre:
        raise ImproperlyConfigured(
            "HORARIO_OPERATIVO_INICIO debe ser anterior a "
            "HORARIO_OPERATIVO_FIN."
        )
    return apertura, cierre


def _normalizar_ahora(ahora):
    if ahora is None:
        return timezone.now()
    if timezone.is_naive(ahora):
        return timezone.make_aware(ahora, timezone.get_current_timezone())
    return ahora


def _inicio_reserva(reserva):
    """Combina la fecha y la hora de inicio en la zona horaria activa."""
    return timezone.make_aware(
        datetime.combine(reserva.fecha, reserva.hora_inicio),
        timezone.get_current_timezone(),
    )


def motivo_no_cancelable(*, reserva, ahora=None):
    """Devuelve el motivo por el que ``reserva`` no puede cancelarse.

    Retorna ``None`` cuando la reserva está ``PENDIENTE`` o ``APROBADA`` y su
    hora de inicio todavía no comenzó. En cualquier otro caso devuelve un
    mensaje específico para que la vista explique el bloqueo.
    """
    if reserva.estado == EstadoReserva.CANCELADA:
        return MOTIVO_YA_CANCELADA
    if reserva.estado == EstadoReserva.RECHAZADA:
        return MOTIVO_RECHAZADA
    if reserva.estado not in (
        EstadoReserva.PENDIENTE,
        EstadoReserva.APROBADA,
    ):
        return MOTIVO_ESTADO_NO_CANCELABLE
    if _normalizar_ahora(ahora) >= _inicio_reserva(reserva):
        return MOTIVO_YA_INICIADA
    return None


def reserva_es_cancelable(*, reserva, ahora=None):
    """Indica si ``reserva`` puede cancelarse en el instante indicado."""
    return motivo_no_cancelable(reserva=reserva, ahora=ahora) is None


def _registrar_historial(
    *,
    reserva,
    estado_anterior,
    estado_nuevo,
    actor,
    observacion="",
    fecha_evento=None,
):
    """Crea un evento de historial dentro de la transacción del llamador.

    Es privado: solo los servicios de ``reservations`` escriben historial. Si
    no hay una transacción activa lanza ``RuntimeError`` para evitar un evento
    huérfano. No abre transacciones ni captura excepciones.
    """
    if not connection.in_atomic_block:
        raise RuntimeError(
            "El historial solo puede registrarse dentro de una transacción."
        )

    datos = {
        "reserva": reserva,
        "estado_anterior": estado_anterior,
        "estado_nuevo": estado_nuevo,
        "actor": actor,
        "observacion": observacion or "",
    }
    if fecha_evento is not None:
        datos["fecha_evento"] = fecha_evento

    return HistorialReserva.objects.create(**datos)


def validar_solicitud(
    *,
    espacio,
    fecha,
    hora_inicio,
    hora_fin,
    motivo,
    ahora=None,
):
    """Valida una solicitud y lanza ``ValidationError`` con claves de campo."""
    errores = {}

    if hora_fin <= hora_inicio:
        errores["hora_fin"] = MENSAJE_HORA_FIN

    motivo_normalizado = (motivo or "").strip()
    if not motivo_normalizado:
        errores["motivo"] = MENSAJE_MOTIVO_VACIO
    elif len(motivo_normalizado) > 255:
        errores["motivo"] = MENSAJE_MOTIVO_LARGO

    if espacio is None or not getattr(espacio, "activo", False):
        errores["espacio"] = MENSAJE_ESPACIO_INACTIVO

    inicio = timezone.make_aware(
        datetime.combine(fecha, hora_inicio),
        timezone.get_current_timezone(),
    )
    if inicio < _normalizar_ahora(ahora):
        errores["hora_inicio"] = MENSAJE_INICIO_PASADO

    apertura, cierre = obtener_horario_operativo()
    if hora_inicio < apertura:
        errores["hora_inicio"] = (
            f"La hora de inicio no puede ser anterior a las {apertura:%H:%M}."
        )
    if hora_fin > cierre:
        errores["hora_fin"] = (
            f"La hora de fin no puede ser posterior a las {cierre:%H:%M}."
        )

    if errores:
        raise ValidationError(errores)


def validar_disponibilidad(
    *,
    espacio,
    fecha,
    hora_inicio,
    hora_fin,
    excluir_reserva=None,
):
    """Rechaza una franja que se cruce con una reserva aprobada.

    Dos reservas del mismo espacio y fecha se cruzan cuando
    ``inicio_A < fin_B`` y ``fin_A > inicio_B``. Las desigualdades estrictas
    permiten la contigüidad exacta. Solo las reservas ``APROBADA`` bloquean.

    ``excluir_reserva`` evita que una reserva se considere en conflicto
    consigo misma al revalidar una aprobación.
    """
    conflictos = Reserva.objects.filter(
        espacio=espacio,
        fecha=fecha,
        estado=EstadoReserva.APROBADA,
        hora_inicio__lt=hora_fin,
        hora_fin__gt=hora_inicio,
    )
    if excluir_reserva is not None:
        conflictos = conflictos.exclude(pk=excluir_reserva)

    conflicto = conflictos.order_by("hora_inicio").first()
    if conflicto is not None:
        raise ValidationError(
            {
                "hora_inicio": (
                    f"El espacio {espacio.nombre} ya está reservado el "
                    f"{fecha} de {conflicto.hora_inicio:%H:%M} a "
                    f"{conflicto.hora_fin:%H:%M}."
                )
            }
        )


def franjas_ocupadas(*, espacio, fecha):
    """Reservas aprobadas de un espacio y fecha, ordenadas por inicio.

    Limita los campos a la franja para no exponer al solicitante ni el motivo.
    La consulta se ejecuta en cada petición, sin caché.
    """
    return (
        Reserva.objects.filter(
            espacio=espacio,
            fecha=fecha,
            estado=EstadoReserva.APROBADA,
        )
        .order_by("hora_inicio")
        .only("hora_inicio", "hora_fin")
    )


@transaction.atomic
def crear_solicitud(
    *,
    espacio,
    solicitante,
    fecha,
    hora_inicio,
    hora_fin,
    motivo,
):
    """Crea una solicitud ``PENDIENTE`` revalidando dentro de la transacción.

    El estado inicial no es parametrizable: toda creación pasa por este
    servicio y siempre escribe ``EstadoReserva.PENDIENTE``.
    """
    if espacio is None:
        raise ValidationError({"espacio": MENSAJE_ESPACIO_INEXISTENTE})

    espacio_actual = (
        EspacioAcademico.objects.select_for_update()
        .filter(pk=espacio.pk)
        .first()
    )
    if espacio_actual is None:
        raise ValidationError({"espacio": MENSAJE_ESPACIO_INEXISTENTE})

    validar_solicitud(
        espacio=espacio_actual,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        motivo=motivo,
    )

    validar_disponibilidad(
        espacio=espacio_actual,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
    )

    reserva = Reserva.objects.create(
        espacio=espacio_actual,
        solicitante=solicitante,
        fecha=fecha,
        hora_inicio=hora_inicio,
        hora_fin=hora_fin,
        motivo=(motivo or "").strip(),
        estado=EstadoReserva.PENDIENTE,
    )
    _registrar_historial(
        reserva=reserva,
        estado_anterior=None,
        estado_nuevo=EstadoReserva.PENDIENTE,
        actor=solicitante,
        observacion="",
        fecha_evento=reserva.creado_en,
    )
    return reserva


@transaction.atomic
def _decidir_reserva(
    *,
    reserva,
    actor,
    nuevo_estado,
    motivo_decision="",
    ahora=None,
):
    """Única puerta de entrada para aprobar o rechazar una solicitud.

    La operación completa corre en una transacción atómica. En orden: exige
    un actor autenticado con rol ``APROBADOR`` o ``ADMINISTRADOR``; recarga la
    reserva con ``select_for_update()``; prohíbe la autodecisión; comprueba
    que ``(estado actual, nuevo_estado)`` esté en
    ``TRANSICIONES_APROBACION``; para una aprobación bloquea el espacio y
    revalida el cruce con ``validar_disponibilidad(..., excluir_reserva=pk)``;
    para un rechazo normaliza el motivo y exige que no quede vacío; actualiza
    de forma condicional solo si la reserva sigue ``PENDIENTE`` y fija
    ``estado``, ``revisado_por``, ``motivo_decision``, ``fecha_decision`` y
    ``actualizado_en`` en una sola escritura. Si la actualización condicional
    afecta cero filas, otra transacción decidió primero y se lanza
    ``ValidationError`` sin sobrescribir al revisor. Al final recarga y
    devuelve la reserva.

    ``select_for_update()`` se conserva para PostgreSQL, pero SQLite lo ignora
    y no ofrece bloqueo pesimista real: la transacción, la revalidación
    inmediata y la actualización condicional reducen la ventana de carrera,
    que queda documentada como limitación conocida (R8).
    """
    momento = _normalizar_ahora(ahora)

    if not getattr(actor, "is_authenticated", False) or actor.rol not in (
        Rol.APROBADOR,
        Rol.ADMINISTRADOR,
    ):
        raise PermissionDenied(MENSAJE_DECISOR_REQUERIDO)

    reserva_actual = (
        Reserva.objects.select_for_update()
        .select_related("espacio")
        .filter(pk=reserva.pk)
        .first()
    )
    if reserva_actual is None:
        raise ValidationError({"estado": "La solicitud ya no existe."})

    if actor.pk == reserva_actual.solicitante_id:
        raise PermissionDenied(MENSAJE_AUTODECISION)

    if (reserva_actual.estado, nuevo_estado) not in TRANSICIONES_APROBACION:
        estado_actual = ETIQUETAS_ESTADO[reserva_actual.estado]
        if nuevo_estado == EstadoReserva.APROBADA:
            mensaje = (
                f"{MENSAJE_SOLO_APROBAR_PENDIENTES} "
                f"La solicitud está {estado_actual}."
            )
        else:
            mensaje = (
                f"{MENSAJE_SOLO_RECHAZAR_PENDIENTES} "
                f"La solicitud está {estado_actual}."
            )
        raise ValidationError({"estado": mensaje})

    if nuevo_estado == EstadoReserva.APROBADA:
        EspacioAcademico.objects.select_for_update().get(
            pk=reserva_actual.espacio_id
        )
        validar_disponibilidad(
            espacio=reserva_actual.espacio,
            fecha=reserva_actual.fecha,
            hora_inicio=reserva_actual.hora_inicio,
            hora_fin=reserva_actual.hora_fin,
            excluir_reserva=reserva_actual.pk,
        )
        motivo_decision = ""
    else:
        motivo_decision = (motivo_decision or "").strip()
        if not motivo_decision:
            raise ValidationError({"motivo": MENSAJE_MOTIVO_DECISION_VACIO})

    actualizadas = Reserva.objects.filter(
        pk=reserva_actual.pk,
        estado=EstadoReserva.PENDIENTE,
    ).update(
        estado=nuevo_estado,
        revisado_por=actor,
        motivo_decision=motivo_decision,
        fecha_decision=momento,
        actualizado_en=momento,
    )
    if not actualizadas:
        raise ValidationError({"estado": MENSAJE_YA_DECIDIDA})

    _registrar_historial(
        reserva=reserva_actual,
        estado_anterior=reserva_actual.estado,
        estado_nuevo=nuevo_estado,
        actor=actor,
        observacion=motivo_decision,
        fecha_evento=momento,
    )

    return Reserva.objects.select_related("espacio", "revisado_por").get(
        pk=reserva_actual.pk
    )


def aprobar_reserva(*, reserva, actor, ahora=None):
    """Aprueba una solicitud pendiente y registra al revisor.

    Delega en ``_decidir_reserva``, que ejecuta la transacción atómica,
    bloquea el espacio, revalida la disponibilidad con
    ``validar_disponibilidad(..., excluir_reserva=pk)`` y actualiza de forma
    condicional solo si la solicitud sigue ``PENDIENTE``. Deja
    ``motivo_decision`` vacío y fija ``fecha_decision`` con el instante de la
    aprobación, independiente de ``creado_en`` y ``actualizado_en``.
    ``select_for_update()`` se conserva para PostgreSQL; SQLite lo ignora y la
    carrera residual se mitiga con la transacción y la actualización
    condicional. ``ahora`` es opcional y permite inyectar el instante en las
    pruebas.
    """
    return _decidir_reserva(
        reserva=reserva,
        actor=actor,
        nuevo_estado=EstadoReserva.APROBADA,
        motivo_decision="",
        ahora=ahora,
    )


def rechazar_reserva(*, reserva, actor, motivo, ahora=None):
    """Rechaza una solicitud pendiente con un motivo obligatorio.

    Delega en ``_decidir_reserva``: la transacción atómica, la comprobación de
    rol, la prohibición de autodecisión y la actualización condicional por
    ``estado=PENDIENTE`` viven allí. El rechazo no aplica la validación de
    disponibilidad ni bloquea el espacio. El motivo se normaliza con
    ``strip()`` y no se acepta vacío ni compuesto solo por espacios o saltos
    de línea; el error queda asociado al campo ``motivo``. Registra revisor,
    motivo normalizado y ``fecha_decision`` en la misma escritura. En SQLite
    ``select_for_update()`` se ignora; la actualización condicional evita
    sobrescribir una decisión previa. ``ahora`` es opcional y permite inyectar
    el instante en las pruebas.
    """
    return _decidir_reserva(
        reserva=reserva,
        actor=actor,
        nuevo_estado=EstadoReserva.RECHAZADA,
        motivo_decision=motivo,
        ahora=ahora,
    )


@transaction.atomic
def cancelar_reserva(*, reserva, actor, ahora=None, observacion=""):
    """Cancela una reserva propia o cualquiera si el actor es administrador.

    La operación completa corre en una transacción atómica. En orden: exige un
    actor autenticado; recarga la reserva con ``select_for_update()``;
    autoriza con ``puede_cancelar_reserva``; comprueba que
    ``(estado actual, CANCELADA)`` esté en ``TRANSICIONES_CANCELACION``;
    rechaza la cancelación cuando la hora de inicio ya comenzó (el instante
    exacto cuenta como iniciada); bloquea el espacio; actualiza de forma
    condicional solo si la reserva conserva el estado original, escribiendo
    únicamente ``estado`` y ``actualizado_en`` para preservar
    ``fecha_decision``; y registra el evento de historial con ``ahora`` como
    fecha. Si la actualización condicional afecta cero filas, otra operación
    cambió la reserva y se lanza ``ValidationError`` sin crear historial.

    ``select_for_update()`` se conserva para PostgreSQL, pero SQLite lo ignora
    y la carrera residual se reduce con la transacción y la actualización
    condicional (R8).
    """
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied(MENSAJE_CANCELACION_NO_AUTORIZADA)

    momento = _normalizar_ahora(ahora)
    reserva_actual = (
        Reserva.objects.select_for_update()
        .select_related("espacio")
        .get(pk=reserva.pk)
    )

    if not puede_cancelar_reserva(actor, reserva_actual):
        raise PermissionDenied(MENSAJE_CANCELACION_NO_AUTORIZADA)

    estado_original = reserva_actual.estado
    if (estado_original, EstadoReserva.CANCELADA) not in (
        TRANSICIONES_CANCELACION
    ):
        estado_actual = ETIQUETAS_ESTADO[estado_original]
        raise ValidationError(
            {
                "estado": (
                    f"{MENSAJE_SOLO_CANCELAR_ACTIVAS} "
                    f"La reserva está {estado_actual}."
                )
            }
        )

    if momento >= _inicio_reserva(reserva_actual):
        raise ValidationError({"estado": MENSAJE_CANCELACION_INICIADA})

    EspacioAcademico.objects.select_for_update().get(
        pk=reserva_actual.espacio_id
    )

    actualizadas = Reserva.objects.filter(
        pk=reserva_actual.pk,
        estado=estado_original,
    ).update(
        estado=EstadoReserva.CANCELADA,
        actualizado_en=momento,
    )
    if not actualizadas:
        raise ValidationError({"estado": MENSAJE_CANCELACION_CAMBIO})

    _registrar_historial(
        reserva=reserva_actual,
        estado_anterior=estado_original,
        estado_nuevo=EstadoReserva.CANCELADA,
        actor=actor,
        observacion=observacion,
        fecha_evento=momento,
    )

    return Reserva.objects.select_related("espacio", "revisado_por").get(
        pk=reserva_actual.pk
    )
