"""Modelo de solicitudes de reserva de espacios académicos."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q


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
