"""Comando de administración para cargar datos de ejemplo.

Siembra un usuario de demostración por cada rol del sistema y un espacio
académico por cada tipo. Las credenciales son conocidas y sirven **solo para
entorno local**: no deben usarse en ningún despliegue real.

Credenciales de demostración (contraseña ``Demo12345!`` para las tres cuentas):

============================  =========================  ===============
Usuario                       Correo                     Rol
============================  =========================  ===============
``solicitante``               ``solicitante@ejemplo.com``  ``SOLICITANTE``
``aprobador``                 ``aprobador@ejemplo.com``    ``APROBADOR``
``admin``                     ``admin@ejemplo.com``        ``ADMINISTRADOR``
============================  =========================  ===============
"""

from django.core.management.base import BaseCommand

from accounts.models import Usuario
from accounts.roles import Rol
from spaces.choices import TipoEspacio
from spaces.models import EspacioAcademico

CONTRASENA_DEMO = "Demo12345!"

USUARIOS_DEMO = (
    {
        "username": "solicitante",
        "email": "solicitante@ejemplo.com",
        "nombre_completo": "Solicitante Demo",
        "rol": Rol.SOLICITANTE,
    },
    {
        "username": "aprobador",
        "email": "aprobador@ejemplo.com",
        "nombre_completo": "Aprobador Demo",
        "rol": Rol.APROBADOR,
    },
    {
        "username": "admin",
        "email": "admin@ejemplo.com",
        "nombre_completo": "Administrador Demo",
        "rol": Rol.ADMINISTRADOR,
    },
)


ESPACIOS_DEMO = (
    {
        "nombre": "Laboratorio de Química",
        "tipo": TipoEspacio.LABORATORIO,
        "capacidad": 30,
        "ubicacion": "Bloque B, piso 2",
    },
    {
        "nombre": "Auditorio Principal",
        "tipo": TipoEspacio.AUDITORIO,
        "capacidad": 200,
        "ubicacion": "Bloque A, piso 1",
    },
    {
        "nombre": "Sala de Cómputo 1",
        "tipo": TipoEspacio.SALA_COMPUTO,
        "capacidad": 40,
        "ubicacion": "Bloque C, piso 3",
    },
)


def sembrar_usuarios():
    """Crea un usuario de demostración por rol y devuelve (creados, existentes).

    Es idempotente: usa ``username`` como clave natural y no duplica registros
    al ejecutarse varias veces. La contraseña se fija solo al crear la cuenta y
    los datos existentes no se sobrescriben, para no revertir cambios hechos
    desde la administración de usuarios.
    """
    creados = 0
    existentes = 0
    for datos in USUARIOS_DEMO:
        usuario, creado = Usuario.objects.get_or_create(
            username=datos["username"],
            defaults={
                "email": datos["email"],
                "nombre_completo": datos["nombre_completo"],
                "rol": datos["rol"],
            },
        )
        if creado:
            usuario.set_password(CONTRASENA_DEMO)
            usuario.save(update_fields=["password"])
            creados += 1
        else:
            existentes += 1
    return creados, existentes


def sembrar_espacios():
    """Crea un espacio de ejemplo por tipo y devuelve (creados, existentes).

    Es idempotente: usa el nombre como clave natural y no sobrescribe registros
    existentes, de modo que una desactivación hecha desde la interfaz se
    conserva al repetir el comando.
    """
    creados = 0
    existentes = 0
    for datos in ESPACIOS_DEMO:
        _, creado = EspacioAcademico.objects.get_or_create(
            nombre=datos["nombre"],
            defaults={
                "tipo": datos["tipo"],
                "capacidad": datos["capacidad"],
                "ubicacion": datos["ubicacion"],
            },
        )
        if creado:
            creados += 1
        else:
            existentes += 1
    return creados, existentes


class Command(BaseCommand):
    help = (
        "Carga los datos de ejemplo del proyecto de forma idempotente: un "
        "usuario por rol y un espacio por tipo. Credenciales de demostración "
        "solo para entorno local (contraseña Demo12345!): solicitante / "
        "solicitante@ejemplo.com, aprobador / aprobador@ejemplo.com, "
        "admin / admin@ejemplo.com."
    )

    def handle(self, *args, **options):
        usuarios_creados, usuarios_existentes = sembrar_usuarios()
        espacios_creados, espacios_existentes = sembrar_espacios()
        self.stdout.write(
            self.style.SUCCESS(
                "seed_data usuarios: "
                f"{usuarios_creados} creados, {usuarios_existentes} existentes"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "seed_data espacios: "
                f"{espacios_creados} creados, {espacios_existentes} existentes"
            )
        )
