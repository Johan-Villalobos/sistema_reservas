"""Tipos de espacio académico."""

from django.db import models


class TipoEspacio(models.TextChoices):
    """Clasificación permitida para un espacio académico."""

    LABORATORIO = "LABORATORIO", "Laboratorio"
    AUDITORIO = "AUDITORIO", "Auditorio"
    SALA_COMPUTO = "SALA_COMPUTO", "Sala de cómputo"
