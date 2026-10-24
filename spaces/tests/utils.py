"""Utilidades compartidas por las pruebas de espacios."""

from spaces.choices import TipoEspacio
from spaces.models import EspacioAcademico


def crear_espacio(
    nombre="Laboratorio A",
    tipo=TipoEspacio.LABORATORIO,
    capacidad=25,
    activo=True,
    **datos,
):
    """Crea un espacio de prueba con valores por defecto razonables."""
    datos.setdefault("ubicacion", "Bloque A")
    datos.setdefault("descripcion", "")
    return EspacioAcademico.objects.create(
        nombre=nombre,
        tipo=tipo,
        capacidad=capacidad,
        activo=activo,
        **datos,
    )
