"""Pruebas de la gestión de usuarios por el administrador.

Cubre REQ-USR-006, REQ-USR-007 y REQ-USR-008.
"""

from django.test import TestCase
from django.urls import reverse

from accounts.models import Usuario
from accounts.roles import Rol
from accounts.tests.utils import CONTRASENA_PRUEBA, crear_usuario


class GestionUsuariosTests(TestCase):
    """Listado, edición, roles, estado y control de acceso."""

    def setUp(self):
        self.admin = crear_usuario(username="admin", rol=Rol.ADMINISTRADOR)
        self.solicitante = crear_usuario(
            username="solicitante",
            email="solicitante@ejemplo.com",
            nombre_completo="Solicitante Uno",
            rol=Rol.SOLICITANTE,
        )

    def datos_formulario(self, usuario, **cambios):
        datos = {
            "username": usuario.username,
            "email": usuario.email,
            "nombre_completo": usuario.nombre_completo,
            "rol": usuario.rol,
            "is_active": True,
        }
        datos.update(cambios)
        return datos

    def test_req_usr_006_el_administrador_lista_los_usuarios(self):
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse("accounts:usuario_lista"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "solicitante")
        self.assertContains(respuesta, "Solicitante")
        self.assertContains(respuesta, "Activo")

    def test_req_usr_006_el_administrador_cambia_el_rol_de_un_usuario(self):
        self.client.force_login(self.admin)

        respuesta = self.client.post(
            reverse("accounts:usuario_editar", args=[self.solicitante.pk]),
            self.datos_formulario(self.solicitante, rol=Rol.APROBADOR),
        )

        self.assertRedirects(respuesta, reverse("accounts:usuario_lista"))
        self.solicitante.refresh_from_db()
        self.assertEqual(self.solicitante.rol, Rol.APROBADOR)

    def test_req_usr_006_el_administrador_desactiva_a_un_usuario(self):
        self.client.force_login(self.admin)
        datos = self.datos_formulario(self.solicitante)
        datos.pop("is_active")

        respuesta = self.client.post(
            reverse("accounts:usuario_editar", args=[self.solicitante.pk]),
            datos,
        )

        self.assertRedirects(respuesta, reverse("accounts:usuario_lista"))
        self.solicitante.refresh_from_db()
        self.assertFalse(self.solicitante.is_active)
        self.client.logout()
        self.assertFalse(
            self.client.login(
                username=self.solicitante.username,
                password=CONTRASENA_PRUEBA,
            )
        )

    def test_req_usr_006_el_administrador_edita_los_datos_de_un_usuario(self):
        self.client.force_login(self.admin)

        respuesta = self.client.post(
            reverse("accounts:usuario_editar", args=[self.solicitante.pk]),
            self.datos_formulario(
                self.solicitante,
                nombre_completo="Solicitante Editado",
                email="editado@ejemplo.com",
            ),
        )

        self.assertRedirects(respuesta, reverse("accounts:usuario_lista"))
        self.solicitante.refresh_from_db()
        self.assertEqual(self.solicitante.nombre_completo, "Solicitante Editado")
        self.assertEqual(self.solicitante.email, "editado@ejemplo.com")

        listado = self.client.get(reverse("accounts:usuario_lista"))
        self.assertContains(listado, "Solicitante Editado")
        self.assertContains(listado, "editado@ejemplo.com")

    def test_req_usr_007_interfaz_rechaza_desactivar_al_ultimo_administrador(self):
        self.client.force_login(self.admin)
        datos = self.datos_formulario(self.admin)
        datos.pop("is_active")

        respuesta = self.client.post(
            reverse("accounts:usuario_editar", args=[self.admin.pk]),
            datos,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            Usuario.objects.get(pk=self.admin.pk).nombre_completo,
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.rol, Rol.ADMINISTRADOR)

    def test_req_usr_007_interfaz_rechaza_cambiar_el_rol_del_ultimo_administrador(self):
        self.client.force_login(self.admin)

        respuesta = self.client.post(
            reverse("accounts:usuario_editar", args=[self.admin.pk]),
            self.datos_formulario(self.admin, rol=Rol.APROBADOR),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, Rol.ADMINISTRADOR)

    def test_req_usr_008_solicitante_recibe_403_en_la_gestion(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(reverse("accounts:usuario_lista"))

        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn(
            "solicitante@ejemplo.com",
            respuesta.content.decode(),
        )

    def test_req_usr_008_aprobador_recibe_403_en_la_gestion(self):
        aprobador = crear_usuario(username="aprobador", rol=Rol.APROBADOR)
        self.client.force_login(aprobador)

        respuesta = self.client.get(reverse("accounts:usuario_lista"))

        self.assertEqual(respuesta.status_code, 403)

    def test_req_usr_008_anonimo_es_redirigido_al_login_con_next(self):
        respuesta = self.client.get(reverse("accounts:usuario_lista"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta["Location"],
            f"{reverse('accounts:login')}?next={reverse('accounts:usuario_lista')}",
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_req_usr_008_solicitante_recibe_403_al_editar(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("accounts:usuario_editar", args=[self.solicitante.pk])
        )

        self.assertEqual(respuesta.status_code, 403)
