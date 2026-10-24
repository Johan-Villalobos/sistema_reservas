"""Reglas de negocio del catálogo de espacios.

Concentra la normalización del nombre, la detección de duplicados sin distinguir
mayúsculas y la validación de tipo y capacidad. Las vistas y los formularios
solo orquestan estas funciones.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from .choices import TipoEspacio
from .models import EspacioAcademico

MENSAJE_NOMBRE_DUPLICADO = "Ya existe un espacio con este nombre."
MENSAJE_CAPACIDAD_INVALIDA = (
    "La capacidad debe ser un número entero mayor que cero."
)
MENSAJE_TIPO_INVALIDO = "El tipo de espacio no es válido."
CAMPOS_EDITABLES = ("nombre", "tipo", "capacidad", "ubicacion", "descripcion")


def normalizar_nombre(nombre):
    """Recorta extremos y colapsa espacios internos múltiples."""
    return " ".join((nombre or "").split())


def _validar_tipo(tipo):
    if tipo not in TipoEspacio.values:
        raise ValidationError(MENSAJE_TIPO_INVALIDO)


def _validar_capacidad(capacidad):
    if isinstance(capacidad, bool) or not isinstance(capacidad, int) or capacidad < 1:
        raise ValidationError(MENSAJE_CAPACIDAD_INVALIDA)


def _existe_nombre(nombre, excluir_pk=None):
    espacios = EspacioAcademico.objects.filter(nombre__iexact=nombre)
    if excluir_pk is not None:
        espacios = espacios.exclude(pk=excluir_pk)
    return espacios.exists()


def _validar_datos(nombre, tipo, capacidad, excluir_pk=None):
    _validar_tipo(tipo)
    _validar_capacidad(capacidad)
    if _existe_nombre(nombre, excluir_pk=excluir_pk):
        raise ValidationError(MENSAJE_NOMBRE_DUPLICADO)


def crear_espacio(*, nombre, tipo, capacidad, ubicacion, descripcion=""):
    """Crea un espacio validando las invariantes del dominio."""
    nombre = normalizar_nombre(nombre)
    _validar_datos(nombre, tipo, capacidad)

    try:
        return EspacioAcademico.objects.create(
            nombre=nombre,
            tipo=tipo,
            capacidad=capacidad,
            ubicacion=ubicacion,
            descripcion=descripcion,
        )
    except IntegrityError as error:
        raise ValidationError(MENSAJE_NOMBRE_DUPLICADO) from error


def actualizar_espacio(espacio, *, datos_validados):
    """Actualiza un espacio conservando las invariantes del dominio."""
    nombre = normalizar_nombre(datos_validados.get("nombre", espacio.nombre))
    tipo = datos_validados.get("tipo", espacio.tipo)
    capacidad = datos_validados.get("capacidad", espacio.capacidad)
    _validar_datos(nombre, tipo, capacidad, excluir_pk=espacio.pk)

    for campo in CAMPOS_EDITABLES:
        if campo in datos_validados:
            setattr(espacio, campo, datos_validados[campo])
    espacio.nombre = nombre

    try:
        espacio.save()
    except IntegrityError as error:
        raise ValidationError(MENSAJE_NOMBRE_DUPLICADO) from error
    return espacio


def desactivar_espacio(espacio):
    """Desactiva el espacio de forma idempotente, sin eliminarlo."""
    if espacio.activo:
        espacio.activo = False
        espacio.save(update_fields=["activo"])
    return espacio
