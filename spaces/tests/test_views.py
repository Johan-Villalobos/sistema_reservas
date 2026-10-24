"""Pruebas del catálogo, el detalle y la administración de espacios.

Cubre REQ-ESP-001, REQ-ESP-005, REQ-ESP-006, REQ-ESP-007 y REQ-ESP-008.
"""

from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from accounts.roles import Rol
from accounts.tests.utils import crear_usuario
from spaces.choices import TipoEspacio
from spaces.models import EspacioAcademico
from spaces.tests.utils import crear_espacio


class EspacioViewsTests(TestCase):
    """Catálogo, detalle, permisos y desactivación lógica."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = crear_usuario(username="admin_spaces", rol=Rol.ADMINISTRADOR)
        cls.solicitante = crear_usuario(
            username="solicitante_spaces",
            rol=Rol.SOLICITANTE,
        )
        cls.aprobador = crear_usuario(
            username="aprobador_spaces",
            rol=Rol.APROBADOR,
        )

    def datos_espacio(self, **cambios):
        datos = {
            "nombre": "Laboratorio Nuevo",
            "tipo": TipoEspacio.LABORATORIO,
            "capacidad": 25,
            "ubicacion": "Bloque B",
            "descripcion": "Laboratorio de prácticas",
        }
        datos.update(cambios)
        return datos

    def assert_redirige_al_login(self, respuesta, ruta):
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta["Location"],
            f"{reverse('accounts:login')}?next={ruta}",
        )

    # Catálogo y detalle.

    def test_req_esp_007_filtro_por_tipo_devuelve_solo_ese_tipo(self):
        crear_espacio(nombre="Laboratorio 1", tipo=TipoEspacio.LABORATORIO)
        crear_espacio(nombre="Auditorio 1", tipo=TipoEspacio.AUDITORIO)
        crear_espacio(nombre="Sala 1", tipo=TipoEspacio.SALA_COMPUTO)
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("spaces:espacio_lista"),
            {"tipo": TipoEspacio.LABORATORIO},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.context["tipo_seleccionado"],
            TipoEspacio.LABORATORIO,
        )
        self.assertEqual(
            [espacio.nombre for espacio in respuesta.context["espacios"]],
            ["Laboratorio 1"],
        )

    def test_req_esp_007_tipo_invalido_se_ignora(self):
        crear_espacio(nombre="Laboratorio 1")
        crear_espacio(nombre="Auditorio 1", tipo=TipoEspacio.AUDITORIO)
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("spaces:espacio_lista"),
            {"tipo": "INVALIDO"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["tipo_seleccionado"], "")
        self.assertEqual(len(respuesta.context["espacios"]), 2)

    def test_req_esp_007_solicitante_solo_ve_espacios_activos(self):
        crear_espacio(nombre="Activo")
        crear_espacio(nombre="Inactivo", activo=False)
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(reverse("spaces:espacio_lista"))

        nombres = [espacio.nombre for espacio in respuesta.context["espacios"]]
        self.assertIn("Activo", nombres)
        self.assertNotIn("Inactivo", nombres)

    def test_req_esp_007_administrador_ve_tambien_los_inactivos(self):
        crear_espacio(nombre="Activo")
        crear_espacio(nombre="Inactivo", activo=False)
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse("spaces:espacio_lista"))

        nombres = [espacio.nombre for espacio in respuesta.context["espacios"]]
        self.assertIn("Activo", nombres)
        self.assertIn("Inactivo", nombres)
        self.assertContains(respuesta, "Inactivo")

    def test_req_esp_008_detalle_de_espacio_activo(self):
        espacio = crear_espacio(
            nombre="Laboratorio de Química",
            capacidad=30,
            ubicacion="Bloque B, piso 2",
            descripcion="Laboratorio de prácticas",
        )
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("spaces:espacio_detalle", args=[espacio.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Laboratorio de Química")
        self.assertContains(respuesta, "Laboratorio")
        self.assertContains(respuesta, "30")
        self.assertContains(respuesta, "Bloque B, piso 2")
        self.assertContains(respuesta, "Laboratorio de prácticas")
        self.assertContains(respuesta, "Activo")

    def test_req_esp_008_detalle_inexistente_devuelve_404(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("spaces:espacio_detalle", args=[9999])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_req_esp_008_solicitante_no_accede_al_detalle_inactivo(self):
        espacio = crear_espacio(nombre="Inactivo", activo=False)
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("spaces:espacio_detalle", args=[espacio.pk])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_req_esp_006_administrador_accede_al_detalle_inactivo(self):
        espacio = crear_espacio(nombre="Inactivo", activo=False)
        self.client.force_login(self.admin)

        respuesta = self.client.get(
            reverse("spaces:espacio_detalle", args=[espacio.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Inactivo")

    def test_req_esp_005_anonimo_es_redirigido_al_login_con_next(self):
        espacio = crear_espacio()

        listado = self.client.get(reverse("spaces:espacio_lista"))
        detalle = self.client.get(
            reverse("spaces:espacio_detalle", args=[espacio.pk])
        )
        creacion = self.client.get(reverse("spaces:espacio_crear"))

        self.assert_redirige_al_login(listado, reverse("spaces:espacio_lista"))
        self.assert_redirige_al_login(
            detalle,
            reverse("spaces:espacio_detalle", args=[espacio.pk]),
        )
        self.assert_redirige_al_login(creacion, reverse("spaces:espacio_crear"))

    # Administración.

    def test_req_esp_005_solicitante_y_aprobador_reciben_403(self):
        espacio = crear_espacio()

        for usuario in (self.solicitante, self.aprobador):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                self.assertEqual(
                    self.client.get(reverse("spaces:espacio_crear")).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.get(
                        reverse("spaces:espacio_editar", args=[espacio.pk])
                    ).status_code,
                    403,
                )
                self.assertEqual(
                    self.client.post(
                        reverse("spaces:espacio_desactivar", args=[espacio.pk])
                    ).status_code,
                    403,
                )

        espacio.refresh_from_db()
        self.assertTrue(espacio.activo)

    def test_req_esp_005_solicitante_no_crea_espacio_por_post(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("spaces:espacio_crear"),
            self.datos_espacio(),
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(
            EspacioAcademico.objects.filter(nombre="Laboratorio Nuevo").exists()
        )

    def test_req_esp_001_administrador_crea_un_espacio_activo(self):
        self.client.force_login(self.admin)

        respuesta = self.client.post(
            reverse("spaces:espacio_crear"),
            self.datos_espacio(),
        )

        espacio = EspacioAcademico.objects.get(nombre="Laboratorio Nuevo")
        self.assertRedirects(
            respuesta,
            reverse("spaces:espacio_detalle", args=[espacio.pk]),
        )
        self.assertTrue(espacio.activo)
        self.assertEqual(espacio.tipo, TipoEspacio.LABORATORIO)
        self.assertEqual(espacio.capacidad, 25)
        self.assertEqual(espacio.ubicacion, "Bloque B")
        self.assertEqual(espacio.descripcion, "Laboratorio de prácticas")

    def test_req_esp_001_administrador_edita_ubicacion_y_descripcion(self):
        espacio = crear_espacio(
            nombre="Laboratorio A",
            capacidad=25,
            ubicacion="Bloque B",
            descripcion="Original",
        )
        self.client.force_login(self.admin)

        respuesta = self.client.post(
            reverse("spaces:espacio_editar", args=[espacio.pk]),
            self.datos_espacio(
                nombre="Laboratorio A",
                capacidad=25,
                ubicacion="Bloque C",
                descripcion="Actualizada",
            ),
        )

        self.assertRedirects(
            respuesta,
            reverse("spaces:espacio_detalle", args=[espacio.pk]),
        )
        espacio.refresh_from_db()
        self.assertEqual(espacio.ubicacion, "Bloque C")
        self.assertEqual(espacio.descripcion, "Actualizada")
        self.assertEqual(espacio.capacidad, 25)

        detalle = self.client.get(
            reverse("spaces:espacio_detalle", args=[espacio.pk])
        )
        self.assertContains(detalle, "Bloque C")
        self.assertContains(detalle, "Actualizada")

    def test_req_esp_006_administrador_desactiva_y_conserva_el_registro(self):
        espacio = crear_espacio(nombre="Laboratorio A", activo=True)
        self.client.force_login(self.admin)

        respuesta = self.client.post(
            reverse("spaces:espacio_desactivar", args=[espacio.pk])
        )

        self.assertRedirects(respuesta, reverse("spaces:espacio_lista"))
        espacio.refresh_from_db()
        self.assertFalse(espacio.activo)
        self.assertTrue(EspacioAcademico.objects.filter(pk=espacio.pk).exists())

    def test_req_esp_006_desactivacion_es_idempotente_y_get_devuelve_405(self):
        espacio = crear_espacio()
        self.client.force_login(self.admin)

        self.assertEqual(
            self.client.get(
                reverse("spaces:espacio_desactivar", args=[espacio.pk])
            ).status_code,
            405,
        )
        primera = self.client.post(
            reverse("spaces:espacio_desactivar", args=[espacio.pk])
        )
        segunda = self.client.post(
            reverse("spaces:espacio_desactivar", args=[espacio.pk])
        )

        self.assertEqual(primera.status_code, 302)
        self.assertEqual(segunda.status_code, 302)
        self.assertEqual(
            EspacioAcademico.objects.filter(pk=espacio.pk).count(),
            1,
        )

    def test_req_esp_006_espacio_desactivado_desaparece_para_solicitante(self):
        espacio = crear_espacio(nombre="Laboratorio A", activo=True)
        self.client.force_login(self.admin)
        self.client.post(
            reverse("spaces:espacio_desactivar", args=[espacio.pk])
        )

        self.client.force_login(self.solicitante)
        respuesta = self.client.get(reverse("spaces:espacio_lista"))

        self.assertNotIn(
            espacio,
            respuesta.context["espacios"],
        )

    def test_req_esp_006_no_existe_ruta_de_eliminacion_fisica(self):
        espacio = crear_espacio()

        with self.assertRaises(NoReverseMatch):
            reverse("spaces:espacio_eliminar", args=[espacio.pk])
