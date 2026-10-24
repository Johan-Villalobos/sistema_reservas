"""Pruebas de cancelación de reservas y liberación de disponibilidad.

Cubre REQ-CAN-001 a REQ-CAN-006 desde el servicio, los permisos y el cliente
HTTP.
"""

from datetime import datetime, time, timedelta
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import Rol
from reservations.models import EstadoReserva, HistorialReserva, Reserva
from reservations.permissions import puede_cancelar_reserva, puede_ver_historial
from reservations.services import (
    MENSAJE_CANCELACION_CAMBIO,
    aprobar_reserva,
    cancelar_reserva,
    franjas_ocupadas,
    motivo_no_cancelable,
    reserva_es_cancelable,
    validar_disponibilidad,
)
from reservations.tests.utils import (
    crear_espacio,
    crear_reserva,
    crear_usuario,
    fecha_futura,
    fecha_pasada,
)


class CancelacionBaseTests(TestCase):
    """Escenario compartido por las pruebas de cancelación."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio(nombre="Auditorio de cancelaciones")
        cls.otro_espacio = crear_espacio(nombre="Sala de cancelaciones")
        cls.solicitante = crear_usuario(
            rol=Rol.SOLICITANTE,
            username="cancel_solicitante",
            nombre_completo="Sofía Solicitante",
        )
        cls.otro_solicitante = crear_usuario(
            rol=Rol.SOLICITANTE,
            username="cancel_otro",
            nombre_completo="Otro Solicitante",
        )
        cls.aprobador = crear_usuario(
            rol=Rol.APROBADOR,
            username="cancel_aprobador",
            nombre_completo="Arturo Aprobador",
        )
        cls.administrador = crear_usuario(
            rol=Rol.ADMINISTRADOR,
            username="cancel_admin",
            nombre_completo="Alicia Administradora",
        )
        cls.fecha = fecha_futura(20)
        cls.fecha_alterna = fecha_futura(21)

    def crear(self, **cambios):
        datos = {
            "espacio": self.espacio,
            "solicitante": self.solicitante,
            "fecha": self.fecha,
            "hora_inicio": time(10, 0),
            "hora_fin": time(11, 0),
            "motivo": "Reserva de cancelación",
        }
        datos.update(cambios)
        return crear_reserva(**datos)

    def inicio(self, reserva):
        return timezone.make_aware(
            datetime.combine(reserva.fecha, reserva.hora_inicio),
            timezone.get_current_timezone(),
        )


class CancelacionServicioTests(CancelacionBaseTests):
    """REQ-CAN-001, 002, 003, 004 y 006 desde el servicio."""

    # REQ-CAN-001: cancelación por el solicitante.

    def test_req_can_001_solicitante_cancela_pendiente(self):
        reserva = self.crear()
        datos_originales = {
            "espacio": reserva.espacio_id,
            "solicitante": reserva.solicitante_id,
            "fecha": reserva.fecha,
            "hora_inicio": reserva.hora_inicio,
            "hora_fin": reserva.hora_fin,
            "motivo": reserva.motivo,
            "fecha_decision": reserva.fecha_decision,
        }

        cancelada = cancelar_reserva(
            reserva=reserva,
            actor=self.solicitante,
        )

        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)
        self.assertEqual(cancelada.espacio_id, datos_originales["espacio"])
        self.assertEqual(cancelada.solicitante_id, datos_originales["solicitante"])
        self.assertEqual(cancelada.fecha, datos_originales["fecha"])
        self.assertEqual(cancelada.hora_inicio, datos_originales["hora_inicio"])
        self.assertEqual(cancelada.hora_fin, datos_originales["hora_fin"])
        self.assertEqual(cancelada.motivo, datos_originales["motivo"])
        self.assertIsNone(cancelada.fecha_decision)
        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.estado_anterior, EstadoReserva.PENDIENTE)
        self.assertEqual(evento.estado_nuevo, EstadoReserva.CANCELADA)
        self.assertEqual(evento.actor, self.solicitante)

    def test_req_can_001_solicitante_cancela_aprobada_y_conserva_fecha_decision(
        self,
    ):
        decision = timezone.now() - timedelta(days=1)
        reserva = self.crear(
            estado=EstadoReserva.APROBADA,
            revisado_por=self.aprobador,
            motivo_decision="",
            fecha_decision=decision,
        )

        cancelada = cancelar_reserva(
            reserva=reserva,
            actor=self.solicitante,
        )

        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)
        self.assertEqual(cancelada.fecha_decision, decision)
        self.assertEqual(cancelada.revisado_por, self.aprobador)
        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.estado_anterior, EstadoReserva.APROBADA)
        self.assertEqual(evento.estado_nuevo, EstadoReserva.CANCELADA)

    def test_req_can_001_conserva_los_datos_originales_de_la_reserva(self):
        reserva = self.crear(motivo="Motivo original que no debe cambiar")
        actualizacion_previa = reserva.actualizado_en

        cancelada = cancelar_reserva(
            reserva=reserva,
            actor=self.solicitante,
        )

        self.assertEqual(cancelada.motivo, "Motivo original que no debe cambiar")
        self.assertEqual(cancelada.espacio, self.espacio)
        self.assertEqual(cancelada.solicitante, self.solicitante)
        self.assertEqual(cancelada.fecha, self.fecha)
        self.assertEqual(cancelada.hora_inicio, time(10, 0))
        self.assertEqual(cancelada.hora_fin, time(11, 0))
        self.assertGreater(cancelada.actualizado_en, actualizacion_previa)

    def test_req_can_001_aprobador_cancela_su_propia_reserva(self):
        reserva = self.crear(solicitante=self.aprobador)

        cancelada = cancelar_reserva(
            reserva=reserva,
            actor=self.aprobador,
        )

        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)
        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.actor, self.aprobador)

    # REQ-CAN-002: cancelación por el administrador.

    def test_req_can_002_administrador_cancela_ajena_pendiente(self):
        reserva = self.crear(fecha=self.fecha_alterna)

        cancelada = cancelar_reserva(
            reserva=reserva,
            actor=self.administrador,
        )

        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)
        self.assertEqual(cancelada.solicitante, self.solicitante)
        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.estado_anterior, EstadoReserva.PENDIENTE)
        self.assertEqual(evento.estado_nuevo, EstadoReserva.CANCELADA)
        self.assertEqual(evento.actor, self.administrador)

    def test_req_can_002_administrador_cancela_ajena_aprobada(self):
        reserva = self.crear(
            fecha=self.fecha_alterna,
            estado=EstadoReserva.APROBADA,
            revisado_por=self.aprobador,
            fecha_decision=timezone.now() - timedelta(hours=1),
        )

        cancelada = cancelar_reserva(
            reserva=reserva,
            actor=self.administrador,
        )

        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)
        self.assertEqual(cancelada.solicitante, self.solicitante)
        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.estado_anterior, EstadoReserva.APROBADA)
        self.assertEqual(evento.actor, self.administrador)

    def test_req_can_002_administrador_cancela_su_propia_reserva(self):
        reserva = self.crear(
            solicitante=self.administrador,
            fecha=self.fecha_alterna,
        )

        cancelada = cancelar_reserva(
            reserva=reserva,
            actor=self.administrador,
        )

        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)
        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.actor, self.administrador)
        self.assertEqual(evento.reserva.solicitante, self.administrador)

    # REQ-CAN-003: estados no cancelables.

    def test_req_can_003_solicitante_no_cancela_rechazada(self):
        reserva = self.crear(estado=EstadoReserva.RECHAZADA)

        with self.assertRaises(ValidationError) as contexto:
            cancelar_reserva(reserva=reserva, actor=self.solicitante)

        self.assertIn("estado", contexto.exception.message_dict)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.RECHAZADA)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_003_solicitante_no_cancela_ya_cancelada(self):
        reserva = self.crear(estado=EstadoReserva.CANCELADA)

        with self.assertRaises(ValidationError):
            cancelar_reserva(reserva=reserva, actor=self.solicitante)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.CANCELADA)
        self.assertEqual(
            HistorialReserva.objects.filter(
                reserva=reserva,
                estado_nuevo=EstadoReserva.CANCELADA,
            ).count(),
            0,
        )

    def test_req_can_003_administrador_tampoco_cancela_rechazada_ni_cancelada(
        self,
    ):
        rechazada = self.crear(
            estado=EstadoReserva.RECHAZADA,
            fecha=self.fecha,
        )
        cancelada = self.crear(
            estado=EstadoReserva.CANCELADA,
            fecha=self.fecha_alterna,
        )

        for reserva in (rechazada, cancelada):
            with self.subTest(estado=reserva.estado):
                with self.assertRaises(ValidationError):
                    cancelar_reserva(
                        reserva=reserva,
                        actor=self.administrador,
                    )
                reserva.refresh_from_db()
                self.assertFalse(
                    HistorialReserva.objects.filter(reserva=reserva).exists()
                )

        self.assertEqual(rechazada.estado, EstadoReserva.RECHAZADA)
        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)

    # REQ-CAN-004: reservas ya iniciadas.

    def test_req_can_004_un_minuto_antes_del_inicio_se_acepta(self):
        reserva = self.crear()
        ahora = self.inicio(reserva) - timedelta(minutes=1)

        cancelada = cancelar_reserva(
            reserva=reserva,
            actor=self.solicitante,
            ahora=ahora,
        )

        self.assertEqual(cancelada.estado, EstadoReserva.CANCELADA)
        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.fecha_evento, ahora)

    def test_req_can_004_instante_exacto_del_inicio_falla(self):
        reserva = self.crear()
        ahora = self.inicio(reserva)

        with self.assertRaises(ValidationError) as contexto:
            cancelar_reserva(
                reserva=reserva,
                actor=self.solicitante,
                ahora=ahora,
            )

        self.assertIn("estado", contexto.exception.message_dict)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_004_despues_del_inicio_falla(self):
        reserva = self.crear()
        ahora = self.inicio(reserva) + timedelta(minutes=1)

        with self.assertRaises(ValidationError):
            cancelar_reserva(
                reserva=reserva,
                actor=self.solicitante,
                ahora=ahora,
            )

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_004_fecha_pasada_falla(self):
        reserva = self.crear(fecha=fecha_pasada(2))

        with self.assertRaises(ValidationError):
            cancelar_reserva(reserva=reserva, actor=self.solicitante)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)

    def test_req_can_004_motivo_y_estado_reportan_el_bloqueo(self):
        pendiente_futura = self.crear()
        iniciada = self.crear(
            fecha=fecha_pasada(1),
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
        )
        rechazada = self.crear(
            estado=EstadoReserva.RECHAZADA,
            fecha=self.fecha_alterna,
        )
        cancelada = self.crear(
            estado=EstadoReserva.CANCELADA,
            fecha=fecha_futura(22),
        )

        self.assertIsNone(motivo_no_cancelable(reserva=pendiente_futura))
        self.assertTrue(reserva_es_cancelable(reserva=pendiente_futura))
        self.assertEqual(
            motivo_no_cancelable(reserva=iniciada),
            "La reserva ya inició",
        )
        self.assertEqual(
            motivo_no_cancelable(reserva=rechazada),
            "La reserva fue rechazada",
        )
        self.assertEqual(
            motivo_no_cancelable(reserva=cancelada),
            "La reserva ya está cancelada",
        )
        self.assertFalse(reserva_es_cancelable(reserva=iniciada))

    # REQ-CAN-006: prohibición de cancelar reservas ajenas.

    def test_req_can_006_otro_solicitante_no_puede_cancelar(self):
        reserva = self.crear()

        with self.assertRaises(PermissionDenied):
            cancelar_reserva(reserva=reserva, actor=self.otro_solicitante)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_006_aprobador_no_propietario_no_puede_cancelar(self):
        reserva = self.crear()

        with self.assertRaises(PermissionDenied):
            cancelar_reserva(reserva=reserva, actor=self.aprobador)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_006_actor_anonimo_no_puede_cancelar(self):
        reserva = self.crear()

        with self.assertRaises(PermissionDenied):
            cancelar_reserva(reserva=reserva, actor=AnonymousUser())

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)

    def test_req_can_006_actualizacion_condicional_con_cero_filas_falla(self):
        reserva = self.crear()

        with mock.patch(
            "django.db.models.query.QuerySet.update",
            return_value=0,
        ):
            with self.assertRaises(ValidationError) as contexto:
                cancelar_reserva(
                    reserva=reserva,
                    actor=self.solicitante,
                )

        self.assertEqual(
            contexto.exception.message_dict["estado"][0],
            MENSAJE_CANCELACION_CAMBIO,
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_006_permisos_de_cancelacion_e_historial(self):
        reserva = self.crear()

        self.assertTrue(puede_cancelar_reserva(self.solicitante, reserva))
        self.assertTrue(puede_cancelar_reserva(self.administrador, reserva))
        self.assertFalse(puede_cancelar_reserva(self.otro_solicitante, reserva))
        self.assertFalse(puede_cancelar_reserva(self.aprobador, reserva))
        self.assertFalse(
            puede_cancelar_reserva(AnonymousUser(), reserva)
        )

        self.assertTrue(puede_ver_historial(self.solicitante, reserva))
        self.assertTrue(puede_ver_historial(self.administrador, reserva))
        self.assertFalse(puede_ver_historial(self.otro_solicitante, reserva))
        self.assertFalse(puede_ver_historial(self.aprobador, reserva))
        self.assertFalse(puede_ver_historial(AnonymousUser(), reserva))


class LiberacionDisponibilidadTests(CancelacionBaseTests):
    """REQ-CAN-005: cancelar una aprobada libera la franja."""

    def test_req_can_005_cancelar_aprobada_libera_la_franja(self):
        reserva = self.crear(
            estado=EstadoReserva.APROBADA,
            revisado_por=self.aprobador,
        )
        with self.assertRaises(ValidationError):
            validar_disponibilidad(
                espacio=self.espacio,
                fecha=self.fecha,
                hora_inicio=time(10, 0),
                hora_fin=time(11, 0),
            )

        cancelar_reserva(reserva=reserva, actor=self.solicitante)

        validar_disponibilidad(
            espacio=self.espacio,
            fecha=self.fecha,
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
        )
        self.assertEqual(
            list(
                franjas_ocupadas(
                    espacio=self.espacio,
                    fecha=self.fecha,
                )
            ),
            [],
        )

    def test_req_can_005_otra_solicitud_puede_aprobarse_tras_cancelar(self):
        primera = self.crear(
            estado=EstadoReserva.APROBADA,
            revisado_por=self.aprobador,
        )
        segunda = self.crear(
            solicitante=self.otro_solicitante,
            hora_inicio=time(10, 30),
            hora_fin=time(11, 30),
        )
        with self.assertRaises(ValidationError):
            aprobar_reserva(reserva=segunda, actor=self.aprobador)

        cancelar_reserva(reserva=primera, actor=self.solicitante)
        aprobada = aprobar_reserva(reserva=segunda, actor=self.aprobador)

        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)
        validar_disponibilidad(
            espacio=self.espacio,
            fecha=self.fecha,
            hora_inicio=time(10, 30),
            hora_fin=time(11, 30),
            excluir_reserva=segunda.pk,
        )

    def test_req_can_005_cancelar_pendiente_no_altera_disponibilidad(self):
        reserva = self.crear()
        self.assertEqual(
            list(
                franjas_ocupadas(
                    espacio=self.espacio,
                    fecha=self.fecha,
                )
            ),
            [],
        )

        cancelar_reserva(reserva=reserva, actor=self.solicitante)

        self.assertEqual(
            list(
                franjas_ocupadas(
                    espacio=self.espacio,
                    fecha=self.fecha,
                )
            ),
            [],
        )
        self.assertTrue(
            HistorialReserva.objects.filter(
                reserva=reserva,
                estado_nuevo=EstadoReserva.CANCELADA,
            ).exists()
        )


class CancelarReservaViewTests(CancelacionBaseTests):
    """REQ-CAN-001 a REQ-CAN-004 y REQ-CAN-006 desde el cliente HTTP."""

    def ruta(self, reserva):
        return reverse("reservations:cancelar", args=[reserva.pk])

    def test_req_can_001_get_confirmacion_muestra_resumen_y_csrf(self):
        reserva = self.crear()
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(self.ruta(reserva))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Resumen de la reserva")
        self.assertContains(respuesta, self.espacio.nombre)
        self.assertContains(respuesta, "Sofía Solicitante")
        self.assertContains(respuesta, reserva.fecha.strftime("%d/%m/%Y"))
        self.assertContains(respuesta, "10:00")
        self.assertContains(respuesta, "11:00")
        self.assertContains(respuesta, reserva.motivo)
        self.assertContains(respuesta, "La cancelación es definitiva")
        self.assertContains(respuesta, "csrfmiddlewaretoken")
        self.assertContains(respuesta, "Confirmar cancelación")

    def test_req_can_001_post_exitoso_redirige_y_crea_historial(self):
        reserva = self.crear()
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(self.ruta(reserva), follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La reserva se canceló correctamente.")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.CANCELADA)
        self.assertTrue(
            HistorialReserva.objects.filter(
                reserva=reserva,
                estado_anterior=EstadoReserva.PENDIENTE,
                estado_nuevo=EstadoReserva.CANCELADA,
                actor=self.solicitante,
            ).exists()
        )

    def test_req_can_002_administrador_cancela_ajena_por_post(self):
        reserva = self.crear()
        self.client.force_login(self.administrador)

        respuesta = self.client.post(self.ruta(reserva), follow=True)

        self.assertEqual(respuesta.status_code, 200)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.CANCELADA)

    def test_req_can_003_post_rechazada_muestra_error_y_no_cambia(self):
        reserva = self.crear(estado=EstadoReserva.RECHAZADA)
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(self.ruta(reserva))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La reserva fue rechazada")
        self.assertNotContains(respuesta, "Confirmar cancelación")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.RECHAZADA)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_003_post_cancelada_muestra_error_y_no_cambia(self):
        reserva = self.crear(estado=EstadoReserva.CANCELADA)
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(self.ruta(reserva))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La reserva ya está cancelada")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.CANCELADA)
        self.assertEqual(
            HistorialReserva.objects.filter(reserva=reserva).count(),
            0,
        )

    def test_req_can_004_post_iniciada_muestra_error_y_no_cambia(self):
        reserva = self.crear(fecha=fecha_pasada(2))
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(self.ruta(reserva))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "La reserva ya inició")
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_006_otro_solicitante_recibe_403(self):
        reserva = self.crear()
        self.client.force_login(self.otro_solicitante)

        get = self.client.get(self.ruta(reserva))
        post = self.client.post(self.ruta(reserva))

        self.assertEqual(get.status_code, 403)
        self.assertEqual(post.status_code, 403)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )

    def test_req_can_006_aprobador_no_propietario_recibe_403(self):
        reserva = self.crear()
        self.client.force_login(self.aprobador)

        get = self.client.get(self.ruta(reserva))
        post = self.client.post(self.ruta(reserva))

        self.assertEqual(get.status_code, 403)
        self.assertEqual(post.status_code, 403)
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)

    def test_req_can_006_anonimo_redirigido_al_login_con_next(self):
        reserva = self.crear()
        ruta = self.ruta(reserva)

        get = self.client.get(ruta)
        post = self.client.post(ruta)

        for respuesta in (get, post):
            self.assertEqual(respuesta.status_code, 302)
            destino = urlparse(respuesta["Location"])
            self.assertEqual(destino.path, reverse("accounts:login"))
            self.assertEqual(parse_qs(destino.query)["next"], [ruta])

    def test_req_can_006_reserva_inexistente_devuelve_404(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:cancelar", args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)

    def test_req_can_001_detalle_solo_ofrece_cancelar_si_es_cancelable(self):
        cancelable = self.crear()
        iniciada = self.crear(
            fecha=fecha_pasada(1),
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
        )
        self.client.force_login(self.solicitante)

        detalle_cancelable = self.client.get(
            reverse("reservations:solicitud_detalle", args=[cancelable.pk])
        )
        detalle_iniciada = self.client.get(
            reverse("reservations:solicitud_detalle", args=[iniciada.pk])
        )

        self.assertContains(detalle_cancelable, "Cancelar reserva")
        self.assertContains(
            detalle_cancelable,
            self.ruta(cancelable),
        )
        self.assertNotContains(detalle_iniciada, "Cancelar reserva")
        self.assertContains(detalle_iniciada, "La reserva ya inició")

    def test_req_can_002_detalle_ajeno_ofrece_cancelar_al_administrador(self):
        reserva = self.crear()
        self.client.force_login(self.administrador)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[reserva.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Cancelar reserva")
        self.assertContains(respuesta, self.ruta(reserva))

    def test_req_can_003_detalle_no_ofrece_cancelar_no_cancelables(self):
        rechazada = self.crear(estado=EstadoReserva.RECHAZADA)
        cancelada = self.crear(
            estado=EstadoReserva.CANCELADA,
            fecha=self.fecha_alterna,
        )
        self.client.force_login(self.solicitante)

        detalle_rechazada = self.client.get(
            reverse("reservations:solicitud_detalle", args=[rechazada.pk])
        )
        detalle_cancelada = self.client.get(
            reverse("reservations:solicitud_detalle", args=[cancelada.pk])
        )

        self.assertNotContains(detalle_rechazada, "Cancelar reserva")
        self.assertContains(detalle_rechazada, "La reserva fue rechazada")
        self.assertNotContains(detalle_cancelada, "Cancelar reserva")
        self.assertContains(detalle_cancelada, "La reserva ya está cancelada")

    def test_req_can_006_ningun_intento_fallido_cambia_estado_ni_historial(
        self,
    ):
        reserva = self.crear(fecha=fecha_pasada(2))
        self.client.force_login(self.solicitante)

        self.client.post(self.ruta(reserva))
        self.client.post(self.ruta(reserva))

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )
