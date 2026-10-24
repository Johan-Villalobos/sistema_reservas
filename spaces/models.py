"""Modelo del catálogo de espacios académicos."""

from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from .choices import TipoEspacio


class EspacioQuerySet(models.QuerySet):
    """Consultas reutilizables sobre el estado lógico de los espacios."""

    def activos(self):
        return self.filter(activo=True)

    def inactivos(self):
        return self.filter(activo=False)


class EspacioAcademico(models.Model):
    """Espacio reservable: laboratorio, auditorio o sala de cómputo."""

    nombre = models.CharField("nombre", max_length=120)
    tipo = models.CharField(
        "tipo",
        max_length=15,
        choices=TipoEspacio.choices,
    )
    capacidad = models.PositiveIntegerField("capacidad")
    ubicacion = models.CharField("ubicación", max_length=150)
    descripcion = models.TextField("descripción", blank=True)
    activo = models.BooleanField("activo", default=True, db_index=True)

    objects = EspacioQuerySet.as_manager()

    class Meta:
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="uniq_espacio_nombre_ci",
            ),
            models.CheckConstraint(
                check=Q(capacidad__gt=0),
                name="ck_espacio_capacidad_positiva",
            ),
        ]

    def save(self, *args, **kwargs):
        # Importación local para evitar el ciclo models <-> services.
        from .services import normalizar_nombre

        self.nombre = normalizar_nombre(self.nombre)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre

    @property
    def tipo_legible(self):
        """Etiqueta legible del tipo según ``TipoEspacio``."""
        return self.get_tipo_display()
