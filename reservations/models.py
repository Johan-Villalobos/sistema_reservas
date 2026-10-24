"""Modelo de solicitudes de reserva de espacios académicos."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

MENSAJE_HISTORIAL_INMUTABLE = "Los registros de historial son inmutables."


class EstadoReserva(models.TextChoices):
    """Estados del ciclo de vida de una reserva."""

    PENDIENTE = "PENDIENTE", "Pendiente"
    APROBADA = "APROBADA", "Aprobada"
    RECHAZADA = "RECHAZADA", "Rechazada"
    CANCELADA = "CANCELADA", "Cancelada"


class Reserva(models.Model):
    """Solicitud de un espacio para una fecha y una franja horaria."""

    espacio = models.ForeignKey(
        "spaces.EspacioAcademico",
        on_delete=models.PROTECT,
        related_name="reservas",
        verbose_name="espacio",
    )
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas_solicitadas",
        verbose_name="solicitante",
    )
    fecha = models.DateField("fecha")
    hora_inicio = models.TimeField("hora de inicio")
    hora_fin = models.TimeField("hora de fin")
    motivo = models.CharField("motivo", max_length=255)
    estado = models.CharField(
        "estado",
        max_length=10,
        choices=EstadoReserva.choices,
        default=EstadoReserva.PENDIENTE,
    )
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservas_revisadas",
        verbose_name="revisado por",
    )
    motivo_decision = models.TextField(
        "motivo de la decisión",
        blank=True,
        default="",
    )
    fecha_decision = models.DateTimeField(
        "fecha de la decisión",
        null=True,
        blank=True,
    )
    creado_en = models.DateTimeField("fecha de creación", auto_now_add=True)
    actualizado_en = models.DateTimeField("actualizado en", auto_now=True)

    class Meta:
        ordering = ["-fecha", "-hora_inicio"]
        constraints = [
            models.CheckConstraint(
                check=Q(hora_fin__gt=F("hora_inicio")),
                name="ck_reserva_hora_fin_mayor",
            ),
        ]

    def __str__(self):
        return (
            f"{self.espacio} · {self.fecha} · "
            f"{self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"
        )


class HistorialReservaQuerySet(models.QuerySet):
    """Queryset que bloquea toda modificación o borrado del historial."""

    def delete(self):
        raise ValidationError(MENSAJE_HISTORIAL_INMUTABLE)

    def update(self, **kwargs):
        raise ValidationError(MENSAJE_HISTORIAL_INMUTABLE)

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError(MENSAJE_HISTORIAL_INMUTABLE)


class HistorialReservaManager(
    models.Manager.from_queryset(HistorialReservaQuerySet)
):
    """Manager del historial con las guardas de inmutabilidad."""


class HistorialReserva(models.Model):
    """Evento inmutable de cambio de estado de una reserva."""

    reserva = models.ForeignKey(
        "Reserva",
        on_delete=models.PROTECT,
        related_name="historial",
        verbose_name="reserva",
    )
    estado_anterior = models.CharField(
        "estado anterior",
        max_length=10,
        choices=EstadoReserva.choices,
        null=True,
        blank=True,
    )
    estado_nuevo = models.CharField(
        "estado nuevo",
        max_length=10,
        choices=EstadoReserva.choices,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="eventos_reserva",
        verbose_name="actor",
    )
    fecha_evento = models.DateTimeField(
        "fecha del evento",
        default=timezone.now,
        editable=False,
    )
    observacion = models.TextField(
        "observación",
        blank=True,
        default="",
    )

    objects = HistorialReservaManager()

    class Meta:
        ordering = ["fecha_evento", "pk"]
        indexes = [
            models.Index(
                fields=["reserva", "fecha_evento"],
                name="hist_reserva_fecha_idx",
            ),
            models.Index(
                fields=["estado_nuevo"],
                name="hist_estado_nuevo_idx",
            ),
            models.Index(
                fields=["fecha_evento"],
                name="hist_fecha_evento_idx",
            ),
        ]

    def __str__(self):
        anterior = (
            self.get_estado_anterior_display()
            if self.estado_anterior
            else "Creación"
        )
        return f"{self.reserva} · {anterior} → {self.get_estado_nuevo_display()}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(MENSAJE_HISTORIAL_INMUTABLE)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(MENSAJE_HISTORIAL_INMUTABLE)
