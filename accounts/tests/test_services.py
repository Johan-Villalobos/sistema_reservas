"""Pruebas de la regla del último administrador activo en el servicio.

Cubre REQ-USR-007 a nivel de regla de negocio.
"""

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Usuario
from accounts.roles import Rol
from accounts.services import (
    MENSAJE_ULTIMO_ADMINISTRADOR,
    actualizar_usuario,
    es_ultimo_administrador_activo,
)
from accounts.tests.utils import crear_usuario


class ServicioUltimoAdministradorTests(TestCase):
    """El servicio conserva al menos un administrador activo."""

    def setUp(self):
        self.admin = crear_usuario(
            username="admin_unico",
            rol=Rol.ADMINISTRADOR,
        )

    def test_req_usr_007_es_ultimo_administrador_activo_detecta_al_unico(self):
        self.assertTrue(es_ultimo_administrador_activo(self.admin))

        crear_usuario(rol=Rol.ADMINISTRADOR)

        self.admin.refresh_from_db()
        self.assertFalse(es_ultimo_administrador_activo(self.admin))

    def test_req_usr_007_rechaza_desactivar_al_ultimo_administrador(self):
        with self.assertRaisesMessage(
            ValidationError,
            MENSAJE_ULTIMO_ADMINISTRADOR,
        ):
            actualizar_usuario(
                self.admin,
                datos_validados={"is_active": False},
                actor=self.admin,
            )

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.rol, Rol.ADMINISTRADOR)

    def test_req_usr_007_rechaza_cambiar_el_rol_del_ultimo_administrador(self):
        with self.assertRaisesMessage(
            ValidationError,
            MENSAJE_ULTIMO_ADMINISTRADOR,
        ):
            actualizar_usuario(
                self.admin,
                datos_validados={"rol": Rol.APROBADOR},
                actor=self.admin,
            )

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, Rol.ADMINISTRADOR)

    def test_req_usr_007_permite_desactivar_con_dos_administradores_activos(self):
        otro_admin = crear_usuario(rol=Rol.ADMINISTRADOR)

        actualizado = actualizar_usuario(
            otro_admin,
            datos_validados={"is_active": False},
            actor=self.admin,
        )

        self.assertFalse(actualizado.is_active)
        self.assertEqual(
            Usuario.objects.filter(rol=Rol.ADMINISTRADOR, is_active=True).count(),
            1,
        )
