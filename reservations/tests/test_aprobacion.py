"""Pruebas del flujo de aprobación y rechazo.

Cubre REQ-APR-001 a REQ-APR-008 desde los servicios y el cliente HTTP.
"""

from datetime import date, time, timedelta
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import Rol
from reservations.models import EstadoReserva, Reserva
from reservations.permissions import puede_decidir_reserva
from reservations.services import (
    MENSAJE_YA_DECIDIDA,
    _decidir_reserva,
    aprobar_reserva,
    rechazar_reserva,
)
from reservations.tests.utils import (
    crear_espacio,
    crear_reserva,
    crear_reserva_aprobada,
    crear_usuario,
)


class DecisionServicioTests(TestCase):
    """Aprobación, rechazo, estados, autodecisión y disponibilidad."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio(nombre="Auditorio de decisiones")
        cls.otro_espacio = crear_espacio(nombre="Sala de decisiones")
        cls.solicitante = crear_usuario(rol=Rol.SOLICITANTE)
        cls.aprobador = crear_usuario(rol=Rol.APROBADOR)
        cls.otro_aprobador = crear_usuario(rol=Rol.APROBADOR)
        cls.administrador = crear_usuario(rol=Rol.ADMINISTRADOR)
        cls.fecha = date.today() + timedelta(days=40)
        cls.fecha_alterna = date.today() + timedelta(days=41)

    def crear_pendiente(self, **cambios):
        datos = {
            "espacio": self.espacio,
            "solicitante": self.solicitante,
            "fecha": self.fecha,
            "hora_inicio": time(10, 0),
            "hora_fin": time(12, 0),
            "motivo": "Solicitud pendiente",
        }
        datos.update(cambios)
        return crear_reserva(**datos)

    def crear_aprobada(self, **cambios):
        datos = {
            "espacio": self.espacio,
            "solicitante": self.solicitante,
            "fecha": self.fecha,
            "hora_inicio": time(10, 0),
            "hora_fin": time(12, 0),
            "motivo": "Reserva aprobada",
        }
        datos.update(cambios)
        return crear_reserva_aprobada(**datos)

    # REQ-APR-002: aprobación.

    def test_req_apr_002_aprobacion_valida_registra_revisor_y_fecha(self):
        pendiente = self.crear_pendiente()
        antes = timezone.now()

        aprobada = aprobar_reserva(reserva=pendiente, actor=self.aprobador)

        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)
        self.assertEqual(aprobada.revisado_por, self.aprobador)
        self.assertIsNotNone(aprobada.fecha_decision)
        self.assertGreaterEqual(aprobada.fecha_decision, antes)
        self.assertEqual(aprobada.motivo_decision, "")
        guardada = Reserva.objects.get(pk=pendiente.pk)
        self.assertEqual(guardada.estado, EstadoReserva.APROBADA)
        self.assertEqual(guardada.revisado_por, self.aprobador)

    def test_req_apr_002_administrador_puede_aprobar(self):
        pendiente = self.crear_pendiente()

        aprobada = aprobar_reserva(
            reserva=pendiente,
            actor=self.administrador,
        )

        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)
        self.assertEqual(aprobada.revisado_por, self.administrador)

    def test_req_apr_002_aprobacion_deja_el_motivo_de_decision_vacio(self):
        reserva = self.crear_pendiente()
        reserva.motivo_decision = "Resto de una decisión previa"
        reserva.save(update_fields=["motivo_decision"])

        aprobada = aprobar_reserva(reserva=reserva, actor=self.aprobador)

        self.assertEqual(aprobada.motivo_decision, "")

    def test_req_apr_002_fecha_decision_independiente_de_actualizado_en(self):
        pendiente = self.crear_pendiente()
        aprobada = aprobar_reserva(reserva=pendiente, actor=self.aprobador)
        decision = aprobada.fecha_decision
        actualizacion_previa = aprobada.actualizado_en

        aprobada.motivo = "Motivo cambiado después de decidir"
        aprobada.save()
        aprobada.refresh_from_db()

        self.assertEqual(aprobada.fecha_decision, decision)
        self.assertGreater(aprobada.actualizado_en, actualizacion_previa)

    # REQ-APR-003: rechazo.

    def test_req_apr_003_rechazo_con_motivo_normaliza_y_registra(self):
        pendiente = self.crear_pendiente()
        antes = timezone.now()

        rechazada = rechazar_reserva(
            reserva=pendiente,
            actor=self.aprobador,
            motivo="  Mantenimiento del auditorio  ",
        )

        self.assertEqual(rechazada.estado, EstadoReserva.RECHAZADA)
        self.assertEqual(rechazada.motivo_decision, "Mantenimiento del auditorio")
        self.assertEqual(rechazada.revisado_por, self.aprobador)
        self.assertGreaterEqual(rechazada.fecha_decision, antes)

    def test_req_apr_003_administrador_puede_rechazar(self):
        pendiente = self.crear_pendiente()

        rechazada = rechazar_reserva(
            reserva=pendiente,
            actor=self.administrador,
            motivo="Sin disponibilidad institucional",
        )

        self.assertEqual(rechazada.estado, EstadoReserva.RECHAZADA)
        self.assertEqual(rechazada.revisado_por, self.administrador)

    def test_req_apr_003_motivo_vacio_es_invalido(self):
        pendiente = self.crear_pendiente()

        with self.assertRaises(ValidationError) as contexto:
            rechazar_reserva(
                reserva=pendiente,
                actor=self.aprobador,
                motivo="",
            )

        self.assertIn("motivo", contexto.exception.message_dict)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(pendiente.revisado_por)
        self.assertEqual(pendiente.motivo_decision, "")
        self.assertIsNone(pendiente.fecha_decision)

    def test_req_apr_003_motivo_solo_espacios_es_invalido(self):
        pendiente = self.crear_pendiente()

        with self.assertRaises(ValidationError) as contexto:
            rechazar_reserva(
                reserva=pendiente,
                actor=self.aprobador,
                motivo="  \n\t   ",
            )

        self.assertIn("motivo", contexto.exception.message_dict)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_003_rechazo_no_exige_disponibilidad(self):
        self.crear_aprobada(
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
        )
        pendiente = self.crear_pendiente(
            hora_inicio=time(11, 0),
            hora_fin=time(13, 0),
        )

        rechazada = rechazar_reserva(
            reserva=pendiente,
            actor=self.aprobador,
            motivo="Se cruza, pero se rechaza",
        )

        self.assertEqual(rechazada.estado, EstadoReserva.RECHAZADA)

    # REQ-APR-004: solo pendientes admiten decisión.

    def test_req_apr_004_aprobar_una_aprobada_falla_sin_cambios(self):
        aprobada = self.crear_aprobada()
        revisor_original = self.otro_aprobador
        aprobada.revisado_por = revisor_original
        aprobada.motivo_decision = ""
        aprobada.fecha_decision = timezone.now() - timedelta(days=1)
        aprobada.save()
        decision_original = aprobada.fecha_decision

        with self.assertRaises(ValidationError) as contexto:
            aprobar_reserva(reserva=aprobada, actor=self.aprobador)

        mensaje = contexto.exception.message_dict["estado"][0]
        self.assertIn("aprobar solicitudes pendientes", mensaje)
        self.assertIn("aprobada", mensaje)
        aprobada.refresh_from_db()
        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)
        self.assertEqual(aprobada.revisado_por, revisor_original)
        self.assertEqual(aprobada.fecha_decision, decision_original)

    def test_req_apr_004_rechazar_una_cancelada_falla_sin_cambios(self):
        cancelada = self.crear_pendiente(estado=EstadoReserva.CANCELADA)

        with self.assertRaises(ValidationError) as contexto:
            rechazar_reserva(
                reserva=cancelada,
                actor=self.aprobador,
                motivo="Intento sobre cancelada",
            )

        mensaje = contexto.exception.message_dict["estado"][0]
        self.assertIn("rechazar solicitudes pendientes", mensaje)
        self.assertIn("cancelada", mensaje)
        cancelada.refresh_from_db()
        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)
        self.assertIsNone(cancelada.revisado_por)
        self.assertEqual(cancelada.motivo_decision, "")

    def test_req_apr_004_aprobar_una_rechazada_falla(self):
        rechazada = self.crear_pendiente(estado=EstadoReserva.RECHAZADA)

        with self.assertRaises(ValidationError) as contexto:
            aprobar_reserva(reserva=rechazada, actor=self.aprobador)

        self.assertIn("estado", contexto.exception.message_dict)
        rechazada.refresh_from_db()
        self.assertEqual(rechazada.estado, EstadoReserva.RECHAZADA)

    def test_req_apr_004_rechazar_una_aprobada_falla(self):
        aprobada = self.crear_aprobada()

        with self.assertRaises(ValidationError) as contexto:
            rechazar_reserva(
                reserva=aprobada,
                actor=self.aprobador,
                motivo="Intento sobre aprobada",
            )

        self.assertIn("estado", contexto.exception.message_dict)
        aprobada.refresh_from_db()
        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)

    def test_req_apr_004_intento_fallido_conserva_la_decision_existente(self):
        pendiente = self.crear_pendiente()
        aprobada = aprobar_reserva(
            reserva=pendiente,
            actor=self.otro_aprobador,
        )
        decision = (
            aprobada.estado,
            aprobada.revisado_por_id,
            aprobada.motivo_decision,
            aprobada.fecha_decision,
        )

        with self.assertRaises(ValidationError):
            rechazar_reserva(
                reserva=aprobada,
                actor=self.administrador,
                motivo="Nuevo intento",
            )

        aprobada.refresh_from_db()
        self.assertEqual(
            (
                aprobada.estado,
                aprobada.revisado_por_id,
                aprobada.motivo_decision,
                aprobada.fecha_decision,
            ),
            decision,
        )

    def test_req_apr_004_actualizacion_condicional_no_sobrescribe(self):
        pendiente = self.crear_pendiente()

        with mock.patch(
            "django.db.models.query.QuerySet.update",
            return_value=0,
        ):
            with self.assertRaises(ValidationError) as contexto:
                aprobar_reserva(reserva=pendiente, actor=self.aprobador)

        self.assertIn("estado", contexto.exception.message_dict)
        self.assertIn(
            MENSAJE_YA_DECIDIDA,
            contexto.exception.message_dict["estado"][0],
        )
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(pendiente.revisado_por)
        self.assertIsNone(pendiente.fecha_decision)

    # REQ-APR-005: autodecisión.

    def test_req_apr_005_aprobador_no_aprueba_su_propia_solicitud(self):
        propia = self.crear_pendiente(solicitante=self.aprobador)

        with self.assertRaises(PermissionDenied):
            aprobar_reserva(reserva=propia, actor=self.aprobador)

        propia.refresh_from_db()
        self.assertEqual(propia.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(propia.revisado_por)

    def test_req_apr_005_aprobador_no_rechaza_su_propia_solicitud(self):
        propia = self.crear_pendiente(solicitante=self.aprobador)

        with self.assertRaises(PermissionDenied):
            rechazar_reserva(
                reserva=propia,
                actor=self.aprobador,
                motivo="Intento de autodecisión",
            )

        propia.refresh_from_db()
        self.assertEqual(propia.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(propia.motivo_decision, "")

    def test_req_apr_005_administrador_no_decide_su_propia_solicitud(self):
        propia = self.crear_pendiente(solicitante=self.administrador)

        with self.assertRaises(PermissionDenied):
            aprobar_reserva(reserva=propia, actor=self.administrador)

        with self.assertRaises(PermissionDenied):
            rechazar_reserva(
                reserva=propia,
                actor=self.administrador,
                motivo="Intento de autodecisión",
            )

        propia.refresh_from_db()
        self.assertEqual(propia.estado, EstadoReserva.PENDIENTE)

    # REQ-APR-006: defensa de rol en el servicio.

    def test_req_apr_006_solicitante_no_puede_decidir(self):
        pendiente = self.crear_pendiente(solicitante=self.otro_aprobador)

        with self.assertRaises(PermissionDenied):
            aprobar_reserva(reserva=pendiente, actor=self.solicitante)

        with self.assertRaises(PermissionDenied):
            rechazar_reserva(
                reserva=pendiente,
                actor=self.solicitante,
                motivo="No autorizado",
            )

        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_006_anonimo_no_puede_decidir(self):
        pendiente = self.crear_pendiente()

        with self.assertRaises(PermissionDenied):
            aprobar_reserva(reserva=pendiente, actor=AnonymousUser())

        with self.assertRaises(PermissionDenied):
            _decidir_reserva(
                reserva=pendiente,
                actor=AnonymousUser(),
                nuevo_estado=EstadoReserva.RECHAZADA,
                motivo_decision="No autorizado",
            )

        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    # REQ-APR-008: disponibilidad al aprobar.

    def test_req_apr_008_conflicto_impide_aprobar_y_deja_pendiente(self):
        self.crear_aprobada(
            hora_inicio=time(11, 0),
            hora_fin=time(13, 0),
        )
        pendiente = self.crear_pendiente()

        with self.assertRaises(ValidationError) as contexto:
            aprobar_reserva(reserva=pendiente, actor=self.aprobador)

        mensaje = contexto.exception.message_dict["hora_inicio"][0]
        self.assertIn(self.espacio.nombre, mensaje)
        self.assertIn(str(self.fecha), mensaje)
        self.assertIn("11:00", mensaje)
        self.assertIn("13:00", mensaje)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(pendiente.revisado_por)
        self.assertIsNone(pendiente.fecha_decision)

    def test_req_apr_008_conflicto_creado_despues_impide_aprobar(self):
        pendiente = self.crear_pendiente()
        self.crear_aprobada(
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
        )

        with self.assertRaises(ValidationError):
            aprobar_reserva(reserva=pendiente, actor=self.aprobador)

        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_008_dos_pendientes_cruzadas_la_segunda_falla(self):
        primera = self.crear_pendiente(
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
        )
        segunda = self.crear_pendiente(
            hora_inicio=time(11, 0),
            hora_fin=time(13, 0),
        )

        aprobar_reserva(reserva=primera, actor=self.aprobador)
        with self.assertRaises(ValidationError):
            aprobar_reserva(reserva=segunda, actor=self.aprobador)

        primera.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(primera.estado, EstadoReserva.APROBADA)
        self.assertEqual(segunda.estado, EstadoReserva.PENDIENTE)


class DecisionViewTestBase(TestCase):
    """Escenario compartido por las pruebas de vistas de decisión."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio(nombre="Auditorio de vistas")
        cls.solicitante = crear_usuario(
            rol=Rol.SOLICITANTE,
            username="solicitante_vistas",
            nombre_completo="Sofía Solicitante",
        )
        cls.aprobador = crear_usuario(
            rol=Rol.APROBADOR,
            username="aprobador_vistas",
            nombre_completo="Arturo Aprobador",
        )
        cls.administrador = crear_usuario(
            rol=Rol.ADMINISTRADOR,
            username="admin_vistas",
            nombre_completo=" Alicia Administradora ",
        )
        cls.otro_solicitante = crear_usuario(
            rol=Rol.SOLICITANTE,
            username="otro_solicitante",
            nombre_completo="Otro Solicitante",
        )
        cls.fecha = date.today() + timedelta(days=60)
        cls.fecha_tardia = date.today() + timedelta(days=61)

    def crear_pendiente(self, **cambios):
        datos = {
            "espacio": self.espacio,
            "solicitante": self.solicitante,
            "fecha": self.fecha,
            "hora_inicio": time(10, 0),
            "hora_fin": time(12, 0),
            "motivo": "Solicitud pendiente de vistas",
        }
        datos.update(cambios)
        return crear_reserva(**datos)

    def crear_estado(self, estado, **cambios):
        cambios["estado"] = estado
        return self.crear_pendiente(**cambios)


class ColaPendientesViewTests(DecisionViewTestBase):
    """REQ-APR-001 y REQ-APR-005 en la cola de pendientes."""

    def test_req_apr_001_aprobador_ve_solo_pendientes_ordenadas(self):
        temprana = self.crear_pendiente(
            fecha=self.fecha,
            hora_inicio=time(9, 0),
            hora_fin=time(10, 0),
            motivo="Pendiente temprana",
        )
        tardia = self.crear_pendiente(
            fecha=self.fecha_tardia,
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
            motivo="Pendiente tardía",
        )
        self.crear_estado(
            EstadoReserva.APROBADA,
            motivo="Aprobada oculta",
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
        )
        self.crear_estado(
            EstadoReserva.RECHAZADA,
            motivo="Rechazada oculta",
            hora_inicio=time(12, 0),
            hora_fin=time(13, 0),
        )
        self.crear_estado(
            EstadoReserva.CANCELADA,
            motivo="Cancelada oculta",
            hora_inicio=time(14, 0),
            hora_fin=time(15, 0),
        )
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(reverse("reservations:pendientes"))

        self.assertEqual(respuesta.status_code, 200)
        solicitudes = list(respuesta.context["solicitudes"])
        self.assertEqual([solicitud.pk for solicitud in solicitudes], [
            temprana.pk,
            tardia.pk,
        ])
        self.assertContains(respuesta, "Pendiente temprana")
        self.assertContains(respuesta, "Pendiente tardía")
        self.assertNotContains(respuesta, "Aprobada oculta")
        self.assertNotContains(respuesta, "Rechazada oculta")
        self.assertNotContains(respuesta, "Cancelada oculta")

    def test_req_apr_001_ordena_por_hora_en_la_misma_fecha(self):
        tarde = self.crear_pendiente(
            hora_inicio=time(14, 0),
            hora_fin=time(15, 0),
        )
        temprana = self.crear_pendiente(
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
        )
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(reverse("reservations:pendientes"))

        self.assertEqual(
            [solicitud.pk for solicitud in respuesta.context["solicitudes"]],
            [temprana.pk, tarde.pk],
        )

    def test_req_apr_001_muestra_espacio_solicitante_fecha_franja_y_motivo(self):
        self.crear_pendiente(motivo="Motivo visible en la cola")
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(reverse("reservations:pendientes"))

        self.assertContains(respuesta, self.espacio.nombre)
        self.assertContains(respuesta, "Sofía Solicitante")
        self.assertContains(respuesta, self.fecha.strftime("%d/%m/%Y"))
        self.assertContains(respuesta, "10:00")
        self.assertContains(respuesta, "12:00")
        self.assertContains(respuesta, "Motivo visible en la cola")

    def test_req_apr_001_administrador_accede_a_la_cola(self):
        self.crear_pendiente(motivo="Visible para administración")
        self.client.force_login(self.administrador)

        respuesta = self.client.get(reverse("reservations:pendientes"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Visible para administración")

    def test_req_apr_001_cola_vacia_muestra_mensaje(self):
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(reverse("reservations:pendientes"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "No hay solicitudes pendientes.")

    def test_req_apr_001_solicitante_recibe_403(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(reverse("reservations:pendientes"))

        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("403.html", [
            plantilla.name for plantilla in respuesta.templates
        ])
        self.assertContains(
            respuesta,
            "No tienes permisos para acceder a esta sección",
            status_code=403,
        )

    def test_req_apr_001_anonimo_redirigido_al_login_con_next(self):
        ruta = reverse("reservations:pendientes")

        respuesta = self.client.get(ruta)

        self.assertEqual(respuesta.status_code, 302)
        destino = urlparse(respuesta["Location"])
        self.assertEqual(destino.path, reverse("accounts:login"))
        self.assertEqual(parse_qs(destino.query)["next"], [ruta])

    def test_req_apr_005_cola_marca_la_solicitud_propia_sin_acciones(self):
        propia = self.crear_pendiente(
            solicitante=self.aprobador,
            motivo="Solicitud propia del aprobador",
        )
        ajena = self.crear_pendiente(
            motivo="Solicitud de otro usuario",
        )
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(reverse("reservations:pendientes"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Solicitud propia del aprobador")
        self.assertContains(respuesta, "Solicitud de otro usuario")
        self.assertContains(
            respuesta,
            "No puedes decidir sobre tu propia solicitud.",
        )
        self.assertNotContains(
            respuesta,
            reverse("reservations:aprobar", args=[propia.pk]),
        )
        self.assertNotContains(
            respuesta,
            reverse("reservations:rechazar", args=[propia.pk]),
        )
        self.assertContains(
            respuesta,
            reverse("reservations:aprobar", args=[ajena.pk]),
        )
        self.assertContains(
            respuesta,
            reverse("reservations:rechazar", args=[ajena.pk]),
        )


class AprobarReservaViewTests(DecisionViewTestBase):
    """REQ-APR-002, REQ-APR-004, REQ-APR-005, REQ-APR-006 y REQ-APR-008."""

    def ruta(self, reserva):
        return reverse("reservations:aprobar", args=[reserva.pk])

    def test_req_apr_002_post_aprueba_y_redirige_a_pendientes(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(self.ruta(pendiente))

        self.assertRedirects(
            respuesta,
            reverse("reservations:pendientes"),
            fetch_redirect_response=False,
        )
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.APROBADA)
        self.assertEqual(pendiente.revisado_por, self.aprobador)

    def test_req_apr_002_administrador_puede_aprobar(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.administrador)

        respuesta = self.client.post(self.ruta(pendiente))

        self.assertEqual(respuesta.status_code, 302)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.APROBADA)
        self.assertEqual(pendiente.revisado_por, self.administrador)

    def test_req_apr_002_get_devuelve_405_y_no_cambia_estado(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(self.ruta(pendiente))

        self.assertEqual(respuesta.status_code, 405)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_002_aprobar_inexistente_devuelve_404(self):
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(
            reverse("reservations:aprobar", args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_req_apr_006_solicitante_aprobar_recibe_403(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(self.ruta(pendiente))

        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(
            respuesta,
            "No tienes permisos para acceder a esta sección",
            status_code=403,
        )
        self.assertNotContains(
            respuesta,
            pendiente.motivo,
            status_code=403,
        )
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_006_anonimo_aprobacion_redirigido_al_login(self):
        pendiente = self.crear_pendiente()
        ruta = self.ruta(pendiente)

        respuesta = self.client.post(ruta)

        self.assertEqual(respuesta.status_code, 302)
        destino = urlparse(respuesta["Location"])
        self.assertEqual(destino.path, reverse("accounts:login"))
        self.assertEqual(parse_qs(destino.query)["next"], [ruta])
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_005_autodecision_recibe_403_y_sigue_pendiente(self):
        propia = self.crear_pendiente(solicitante=self.aprobador)
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(self.ruta(propia))

        self.assertEqual(respuesta.status_code, 403)
        propia.refresh_from_db()
        self.assertEqual(propia.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(propia.revisado_por)

    def test_req_apr_005_administrador_autodecision_recibe_403(self):
        propia = self.crear_pendiente(solicitante=self.administrador)
        self.client.force_login(self.administrador)

        respuesta = self.client.post(self.ruta(propia))

        self.assertEqual(respuesta.status_code, 403)
        propia.refresh_from_db()
        self.assertEqual(propia.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_008_conflicto_muestra_mensaje_y_no_cambia_estado(self):
        self.crear_estado(
            EstadoReserva.APROBADA,
            hora_inicio=time(11, 0),
            hora_fin=time(13, 0),
        )
        pendiente = self.crear_pendiente()
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(self.ruta(pendiente))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.espacio.nombre)
        self.assertContains(respuesta, str(self.fecha))
        self.assertContains(respuesta, "11:00")
        self.assertContains(respuesta, "13:00")
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(pendiente.revisado_por)

    def test_req_apr_004_aprobar_no_pendiente_muestra_mensaje(self):
        aprobada = self.crear_estado(EstadoReserva.APROBADA)
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(self.ruta(aprobada))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Solo se pueden aprobar solicitudes pendientes.",
        )
        aprobada.refresh_from_db()
        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)


class RechazarReservaViewTests(DecisionViewTestBase):
    """REQ-APR-003, REQ-APR-004, REQ-APR-005 y REQ-APR-006."""

    def ruta(self, reserva):
        return reverse("reservations:rechazar", args=[reserva.pk])

    def test_req_apr_006_aprobador_accede_al_formulario_de_rechazo(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(self.ruta(pendiente))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Motivo del rechazo")
        self.assertContains(respuesta, "<textarea")
        self.assertContains(respuesta, self.espacio.nombre)
        self.assertContains(respuesta, pendiente.motivo)

    def test_req_apr_003_post_valido_rechaza_y_redirige(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(
            self.ruta(pendiente),
            {"motivo": "  El espacio estará en mantenimiento  "},
        )

        self.assertRedirects(
            respuesta,
            reverse("reservations:pendientes"),
            fetch_redirect_response=False,
        )
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.RECHAZADA)
        self.assertEqual(
            pendiente.motivo_decision,
            "El espacio estará en mantenimiento",
        )
        self.assertEqual(pendiente.revisado_por, self.aprobador)

    def test_req_apr_003_motivo_vacio_muestra_error_junto_al_campo(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(self.ruta(pendiente), {"motivo": ""})

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("motivo", respuesta.context["form"].errors)
        self.assertContains(respuesta, "El motivo del rechazo es obligatorio.")
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(pendiente.revisado_por)

    def test_req_apr_003_motivo_solo_espacios_muestra_error(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(
            self.ruta(pendiente),
            {"motivo": "  \n\t  "},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("motivo", respuesta.context["form"].errors)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_004_rechazar_no_pendiente_muestra_error(self):
        aprobada = self.crear_estado(EstadoReserva.APROBADA)
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(
            self.ruta(aprobada),
            {"motivo": "Intento sobre una aprobada"},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Solo se pueden rechazar solicitudes pendientes.",
        )
        aprobada.refresh_from_db()
        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)

    def test_req_apr_004_rechazar_inexistente_devuelve_404(self):
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(
            reverse("reservations:rechazar", args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_req_apr_006_solicitante_rechazar_recibe_403(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.solicitante)

        get = self.client.get(self.ruta(pendiente))
        post = self.client.post(
            self.ruta(pendiente),
            {"motivo": "Intento no autorizado"},
        )

        self.assertEqual(get.status_code, 403)
        self.assertEqual(post.status_code, 403)
        self.assertContains(
            get,
            "No tienes permisos para acceder a esta sección",
            status_code=403,
        )
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_apr_006_anonimo_rechazo_redirigido_al_login(self):
        pendiente = self.crear_pendiente()
        ruta = self.ruta(pendiente)

        respuesta = self.client.get(ruta)

        self.assertEqual(respuesta.status_code, 302)
        destino = urlparse(respuesta["Location"])
        self.assertEqual(destino.path, reverse("accounts:login"))
        self.assertEqual(parse_qs(destino.query)["next"], [ruta])

    def test_req_apr_005_autodecision_en_rechazo_recibe_403(self):
        propia = self.crear_pendiente(solicitante=self.aprobador)
        self.client.force_login(self.aprobador)

        get = self.client.get(self.ruta(propia))
        post = self.client.post(
            self.ruta(propia),
            {"motivo": "Intento de autodecisión"},
        )

        self.assertEqual(get.status_code, 403)
        self.assertEqual(post.status_code, 403)
        propia.refresh_from_db()
        self.assertEqual(propia.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(propia.motivo_decision, "")

    def test_req_apr_005_administrador_autodecision_en_rechazo_recibe_403(self):
        propia = self.crear_pendiente(solicitante=self.administrador)
        self.client.force_login(self.administrador)

        get = self.client.get(self.ruta(propia))
        post = self.client.post(
            self.ruta(propia),
            {"motivo": "Intento de autodecisión"},
        )

        self.assertEqual(get.status_code, 403)
        self.assertEqual(post.status_code, 403)
        propia.refresh_from_db()
        self.assertEqual(propia.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(propia.motivo_decision, "")


class DetalleDecisionViewTests(DecisionViewTestBase):
    """REQ-APR-007: visibilidad de la decisión para el solicitante."""

    def test_req_apr_007_solicitante_ve_solicitud_aprobada(self):
        pendiente = self.crear_pendiente()
        aprobar_reserva(reserva=pendiente, actor=self.aprobador)
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[pendiente.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Aprobada")
        self.assertContains(respuesta, "Arturo Aprobador")
        self.assertContains(respuesta, "Revisado por")
        self.assertNotContains(respuesta, "Motivo de la decisión")

    def test_req_apr_007_solicitante_ve_motivo_completo_del_rechazo(self):
        pendiente = self.crear_pendiente()
        rechazar_reserva(
            reserva=pendiente,
            actor=self.aprobador,
            motivo="Primera línea del motivo\nSegunda línea del motivo",
        )
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[pendiente.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Rechazada")
        self.assertContains(respuesta, "Primera línea del motivo")
        self.assertContains(respuesta, "Segunda línea del motivo")
        self.assertContains(respuesta, "Arturo Aprobador")
        self.assertContains(respuesta, "Motivo de la decisión")

    def test_req_apr_007_pendiente_no_muestra_datos_de_decision(self):
        pendiente = self.crear_pendiente()
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[pendiente.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Pendiente")
        self.assertNotContains(respuesta, "Revisado por")
        self.assertNotContains(respuesta, "Motivo de la decisión")

    def test_req_apr_007_otro_solicitante_no_ve_el_detalle(self):
        pendiente = self.crear_pendiente()
        rechazar_reserva(
            reserva=pendiente,
            actor=self.aprobador,
            motivo="Motivo reservado",
        )
        self.client.force_login(self.otro_solicitante)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[pendiente.pk])
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertNotContains(
            respuesta,
            "Motivo reservado",
            status_code=403,
        )


class PermisoDecisionTests(TestCase):
    """REQ-APR-005 y REQ-APR-006: helper de autodecisión y rol."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio(nombre="Auditorio de permisos")
        cls.solicitante = crear_usuario(rol=Rol.SOLICITANTE)
        cls.aprobador = crear_usuario(rol=Rol.APROBADOR)
        cls.administrador = crear_usuario(rol=Rol.ADMINISTRADOR)
        cls.ajena = crear_reserva(
            espacio=cls.espacio,
            solicitante=cls.solicitante,
        )
        cls.propia_aprobador = crear_reserva(
            espacio=cls.espacio,
            solicitante=cls.aprobador,
        )
        cls.propia_administrador = crear_reserva(
            espacio=cls.espacio,
            solicitante=cls.administrador,
        )

    def test_req_apr_006_aprobador_puede_decidir_solicitud_ajena(self):
        self.assertTrue(puede_decidir_reserva(self.aprobador, self.ajena))

    def test_req_apr_006_administrador_puede_decidir_solicitud_ajena(self):
        self.assertTrue(
            puede_decidir_reserva(self.administrador, self.ajena)
        )

    def test_req_apr_006_solicitante_no_puede_decidir(self):
        self.assertFalse(puede_decidir_reserva(self.solicitante, self.ajena))

    def test_req_apr_005_aprobador_no_decide_su_solicitud(self):
        self.assertFalse(
            puede_decidir_reserva(self.aprobador, self.propia_aprobador)
        )

    def test_req_apr_005_administrador_no_decide_su_solicitud(self):
        self.assertFalse(
            puede_decidir_reserva(
                self.administrador,
                self.propia_administrador,
            )
        )

    def test_req_apr_006_anonimo_no_puede_decidir(self):
        self.assertFalse(puede_decidir_reserva(AnonymousUser(), self.ajena))

    def test_req_apr_006_el_estado_no_forma_parte_del_permiso(self):
        self.ajena.estado = EstadoReserva.APROBADA
        self.ajena.save(update_fields=["estado"])

        self.assertTrue(puede_decidir_reserva(self.aprobador, self.ajena))


class IntegracionAprobacionTests(DecisionViewTestBase):
    """REQ-APR-001, REQ-APR-002, REQ-APR-003 y REQ-APR-008 de extremo a extremo."""

    def crear_solicitud_web(self, **cambios):
        datos = {
            "espacio": self.espacio.pk,
            "fecha": self.fecha.isoformat(),
            "hora_inicio": "10:00",
            "hora_fin": "12:00",
            "motivo": "Solicitud creada por el flujo web",
        }
        datos.update(cambios)
        self.client.force_login(self.solicitante)
        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            datos,
        )
        self.assertEqual(respuesta.status_code, 302)
        return Reserva.objects.get(motivo=datos["motivo"])

    def test_req_apr_002_flujo_completo_de_aprobacion(self):
        reserva = self.crear_solicitud_web()

        self.client.force_login(self.aprobador)
        cola = self.client.get(reverse("reservations:pendientes"))
        self.assertContains(cola, reserva.motivo)
        self.assertContains(
            cola,
            reverse("reservations:aprobar", args=[reserva.pk]),
        )

        aprobacion = self.client.post(
            reverse("reservations:aprobar", args=[reserva.pk])
        )
        self.assertRedirects(
            aprobacion,
            reverse("reservations:pendientes"),
            fetch_redirect_response=False,
        )

        self.client.force_login(self.solicitante)
        detalle = self.client.get(
            reverse("reservations:solicitud_detalle", args=[reserva.pk])
        )
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, "Aprobada")
        self.assertContains(detalle, "Arturo Aprobador")
        self.assertContains(detalle, "Revisado por")

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.APROBADA)
        self.assertEqual(reserva.revisado_por, self.aprobador)

    def test_req_apr_003_flujo_completo_de_rechazo_con_motivo(self):
        reserva = self.crear_solicitud_web()
        motivo = "No hay personal disponible\npara abrir el auditorio"

        self.client.force_login(self.aprobador)
        rechazo = self.client.post(
            reverse("reservations:rechazar", args=[reserva.pk]),
            {"motivo": motivo},
        )
        self.assertRedirects(
            rechazo,
            reverse("reservations:pendientes"),
            fetch_redirect_response=False,
        )

        self.client.force_login(self.solicitante)
        detalle = self.client.get(
            reverse("reservations:solicitud_detalle", args=[reserva.pk])
        )
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, "Rechazada")
        self.assertContains(detalle, "No hay personal disponible")
        self.assertContains(detalle, "para abrir el auditorio")
        self.assertContains(detalle, "Arturo Aprobador")
        self.assertContains(detalle, "Motivo de la decisión")

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.RECHAZADA)
        self.assertEqual(reserva.motivo_decision, motivo)
        self.assertEqual(reserva.revisado_por, self.aprobador)

    def test_req_apr_008_dos_pendientes_cruzadas_la_segunda_falla(self):
        primera = self.crear_solicitud_web(
            hora_inicio="10:00",
            hora_fin="12:00",
            motivo="Primera solicitud del flujo",
        )
        segunda = self.crear_solicitud_web(
            hora_inicio="11:00",
            hora_fin="13:00",
            motivo="Segunda solicitud del flujo",
        )
        self.client.force_login(self.aprobador)

        self.client.post(
            reverse("reservations:aprobar", args=[primera.pk])
        )
        respuesta = self.client.post(
            reverse("reservations:aprobar", args=[segunda.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.espacio.nombre)
        self.assertContains(respuesta, str(self.fecha))
        self.assertContains(respuesta, "10:00")
        self.assertContains(respuesta, "12:00")
        primera.refresh_from_db()
        segunda.refresh_from_db()
        self.assertEqual(primera.estado, EstadoReserva.APROBADA)
        self.assertEqual(segunda.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(segunda.revisado_por)

    def test_req_apr_008_reserva_aprobada_creada_despues_impide_aprobar(self):
        pendiente = self.crear_solicitud_web(
            hora_inicio="10:00",
            hora_fin="12:00",
            motivo="Solicitud previa a la reserva aprobada",
        )
        self.crear_estado(
            EstadoReserva.APROBADA,
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
            motivo="Reserva aprobada posterior",
            solicitante=self.otro_solicitante,
        )
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(
            reverse("reservations:aprobar", args=[pendiente.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self.espacio.nombre)
        self.assertContains(respuesta, str(self.fecha))
        self.assertContains(respuesta, "10:00")
        self.assertContains(respuesta, "11:00")
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(pendiente.revisado_por)
