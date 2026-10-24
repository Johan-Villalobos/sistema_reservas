"""Pruebas del modelo de usuario y de las restricciones de correo.

Cubre REQ-USR-001 y REQ-USR-002.
"""

import os
from unittest import mock

from django.core.management import call_command
from django.db import IntegrityError, connection, migrations, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

from accounts.models import Usuario
from accounts.roles import Rol
from accounts.tests.utils import CONTRASENA_PRUEBA, crear_usuario


class ModeloUsuarioTests(TestCase):
    """Campos, rol por defecto, unicidad de correo y métodos del usuario."""

    def test_req_usr_001_usuario_guarda_y_recupera_todos_sus_campos(self):
        usuario = crear_usuario(
            username="ana",
            email="ana@ejemplo.com",
            nombre_completo="Ana Pérez",
            rol=Rol.APROBADOR,
        )

        recuperado = Usuario.objects.get(pk=usuario.pk)

        self.assertEqual(recuperado.username, "ana")
        self.assertEqual(recuperado.email, "ana@ejemplo.com")
        self.assertEqual(recuperado.nombre_completo, "Ana Pérez")
        self.assertEqual(recuperado.rol, Rol.APROBADOR)

    def test_req_usr_001_usuario_queda_activo_por_defecto(self):
        usuario = crear_usuario()

        self.assertTrue(usuario.is_active)

    def test_req_usr_001_rol_por_defecto_es_solicitante(self):
        usuario = Usuario.objects.create_user(
            username="nuevo",
            email="nuevo@ejemplo.com",
            password=CONTRASENA_PRUEBA,
            nombre_completo="Nuevo Usuario",
        )

        self.assertEqual(usuario.rol, Rol.SOLICITANTE)

    def test_req_usr_001_get_full_name_devuelve_el_nombre_completo(self):
        usuario = crear_usuario(nombre_completo="Ana Pérez")

        self.assertEqual(usuario.get_full_name(), "Ana Pérez")

    def test_req_usr_001_es_administrador_solo_para_el_rol_administrador(self):
        admin = crear_usuario(rol=Rol.ADMINISTRADOR)
        solicitante = crear_usuario(rol=Rol.SOLICITANTE)
        aprobador = crear_usuario(rol=Rol.APROBADOR)

        self.assertTrue(admin.es_administrador)
        self.assertFalse(solicitante.es_administrador)
        self.assertFalse(aprobador.es_administrador)

    def test_req_usr_001_el_correo_es_obligatorio(self):
        campo = Usuario._meta.get_field("email")

        self.assertFalse(campo.blank)
        self.assertFalse(campo.null)

    def test_req_usr_001_migracion_en_base_limpia_crea_las_columnas(self):
        columnas = {
            columna.name
            for columna in connection.introspection.get_table_description(
                connection.cursor(),
                "accounts_usuario",
            )
        }
        tablas = set(connection.introspection.table_names())

        self.assertTrue(
            {"username", "email", "nombre_completo", "rol", "is_active"}.issubset(
                columnas
            )
        )
        self.assertNotIn("auth_user", tablas)

    def test_req_usr_001_migracion_inicial_no_se_regenera_y_0002_agrega_campos(self):
        loader = MigrationLoader(connection)
        inicial = loader.disk_migrations[("accounts", "0001_initial")]
        nodo_hoja = next(
            nodo for nodo in loader.graph.leaf_nodes() if nodo[0] == "accounts"
        )
        posterior = loader.disk_migrations[nodo_hoja]

        self.assertTrue(inicial.initial)
        self.assertFalse(
            any(
                isinstance(operacion, migrations.AddField)
                for operacion in inicial.operations
            )
        )
        self.assertIn(("accounts", "0001_initial"), posterior.dependencies)

        campos_agregados = {
            operacion.name
            for operacion in posterior.operations
            if isinstance(operacion, migrations.AddField)
        }
        campos_alterados = {
            operacion.name
            for operacion in posterior.operations
            if isinstance(operacion, migrations.AlterField)
        }
        restricciones = {
            operacion.constraint.name
            for operacion in posterior.operations
            if isinstance(operacion, migrations.AddConstraint)
        }

        self.assertTrue({"nombre_completo", "rol"}.issubset(campos_agregados))
        self.assertIn("email", campos_alterados)
        self.assertIn("uniq_usuario_email_ci", restricciones)

    def test_req_usr_001_createsuperuser_usa_el_modelo_personalizado(self):
        with mock.patch.dict(
            os.environ,
            {"DJANGO_SUPERUSER_PASSWORD": CONTRASENA_PRUEBA},
        ):
            call_command(
                "createsuperuser",
                interactive=False,
                username="superusuario",
                email="superusuario@ejemplo.com",
                nombre_completo="Super Usuario",
                verbosity=0,
            )

        usuario = Usuario.objects.get(username="superusuario")

        self.assertIsInstance(usuario, Usuario)
        self.assertTrue(usuario.is_superuser)
        self.assertTrue(usuario.check_password(CONTRASENA_PRUEBA))

    def test_req_usr_002_correo_unico_insensible_a_mayusculas(self):
        crear_usuario(email="ana@ejemplo.com")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Usuario.objects.create_user(
                    username="ana_mayusculas",
                    email="Ana@Ejemplo.com",
                    password=CONTRASENA_PRUEBA,
                    nombre_completo="Ana Duplicada",
                )

        self.assertEqual(
            Usuario.objects.filter(email__iexact="ana@ejemplo.com").count(),
            1,
        )

    def test_req_usr_002_el_manager_normaliza_el_correo_a_minusculas(self):
        usuario = crear_usuario(email="Ana@Ejemplo.com")

        self.assertEqual(usuario.email, "ana@ejemplo.com")
