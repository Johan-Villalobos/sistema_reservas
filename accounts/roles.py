"""Roles del dominio de cuentas."""

from django.db import models


class Rol(models.TextChoices):
    """Roles disponibles para un usuario del sistema."""

    SOLICITANTE = "SOLICITANTE", "Solicitante"
    APROBADOR = "APROBADOR", "Aprobador"
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
