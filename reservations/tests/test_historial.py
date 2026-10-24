"""Pruebas del historial de reservas.

Cubre REQ-HIS-001 a REQ-HIS-005: registro de transiciones, atomicidad,
inmutabilidad, visibilidad y filtros.
"""

from datetime import datetime, time, timedelta
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import Rol
from reservations.models import EstadoReserva, HistorialReserva, Reserva
from reservations.services import (
    _registrar_historial,
    aprobar_reserva,
    cancelar_reserva,
    crear_solicitud,
    rechazar_reserva,
)
from reservations.tests.utils import (
    crear_espacio,
    crear_historial,
    crear_reserva,
    crear_usuario,
    datos_solicitud,
    fecha_futura,
)


class HistorialBaseTests(TestCase):
    """Escenario compartido por las pruebas del historial."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio(nombre="Auditorio de historial")
        cls.otro_espacio = crear_espacio(nombre="Sala de historial")
        cls.solicitante = crear_usuario(
            rol=Rol.SOLICITANTE,
            username="hist_solicitante",
            nombre_completo="Sofía Solicitante",
        )
        cls.otro_solicitante = crear_usuario(
            rol=Rol.SOLICITANTE,
            username="hist_otro",
            nombre_completo="Otro Solicitante",
        )
        cls.aprobador = crear_usuario(
            rol=Rol.APROBADOR,
            username="hist_aprobador",
            nombre_completo="Arturo Aprobador",
        )
        cls.administrador = crear_usuario(
            rol=Rol.ADMINISTRADOR,
            username="hist_admin",
            nombre_completo="Alicia Administradora",
        )
        cls.fecha = fecha_futura(30)
        cls.fecha_alterna = fecha_futura(31)

    def crear(self, **cambios):
        datos = {
            "espacio": self.espacio,
            "solicitante": self.solicitante,
            "fecha": self.fecha,
            "hora_inicio": time(10, 0),
            "hora_fin": time(11, 0),
            "motivo": "Reserva de historial",
        }
        datos.update(cambios)
        return crear_reserva(**datos)


class HistorialRegistroTests(HistorialBaseTests):
    """REQ-HIS-001: cada transición crea su evento."""

    def test_req_his_001_creacion_registra_evento_inicial(self):
        datos = datos_solicitud(
            fecha=self.fecha,
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
            motivo="Creación con historial",
        )
        reserva = crear_solicitud(
            espacio=self.espacio,
            solicitante=self.solicitante,
            **datos,
        )

        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertIsNone(evento.estado_anterior)
        self.assertEqual(evento.estado_nuevo, EstadoReserva.PENDIENTE)
        self.assertEqual(evento.actor, self.solicitante)
        self.assertIsNotNone(evento.fecha_evento)
        self.assertEqual(evento.fecha_evento, reserva.creado_en)
        self.assertEqual(evento.observacion, "")

    def test_req_his_001_aprobacion_registra_evento(self):
        reserva = self.crear()

        aprobada = aprobar_reserva(
            reserva=reserva,
            actor=self.aprobador,
        )

        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)
        self.assertEqual(evento.estado_anterior, EstadoReserva.PENDIENTE)
        self.assertEqual(evento.estado_nuevo, EstadoReserva.APROBADA)
        self.assertEqual(evento.actor, self.aprobador)
        self.assertEqual(evento.observacion, "")
        self.assertIsNotNone(evento.fecha_evento)

    def test_req_his_001_rechazo_registra_motivo_como_observacion(self):
        reserva = self.crear()

        rechazada = rechazar_reserva(
            reserva=reserva,
            actor=self.aprobador,
            motivo="  Mantenimiento del auditorio  ",
        )

        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(rechazada.estado, EstadoReserva.RECHAZADA)
        self.assertEqual(evento.estado_anterior, EstadoReserva.PENDIENTE)
        self.assertEqual(evento.estado_nuevo, EstadoReserva.RECHAZADA)
        self.assertEqual(evento.actor, self.aprobador)
        self.assertEqual(evento.observacion, "Mantenimiento del auditorio")

    def test_req_his_001_cancelacion_desde_pendiente_registra_evento(self):
        reserva = self.crear()

        cancelar_reserva(reserva=reserva, actor=self.solicitante)

        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.estado_anterior, EstadoReserva.PENDIENTE)
        self.assertEqual(evento.estado_nuevo, EstadoReserva.CANCELADA)
        self.assertEqual(evento.actor, self.solicitante)
        self.assertIsNotNone(evento.fecha_evento)

    def test_req_his_001_cancelacion_desde_aprobada_registra_evento(self):
        reserva = self.crear(
            estado=EstadoReserva.APROBADA,
            revisado_por=self.aprobador,
            fecha_decision=timezone.now() - timedelta(hours=2),
        )

        cancelar_reserva(reserva=reserva, actor=self.solicitante)

        evento = HistorialReserva.objects.get(reserva=reserva)
        self.assertEqual(evento.estado_anterior, EstadoReserva.APROBADA)
        self.assertEqual(evento.estado_nuevo, EstadoReserva.CANCELADA)
        self.assertEqual(evento.actor, self.solicitante)

    def test_req_his_001_transicion_invalida_no_crea_evento(self):
        aprobada = self.crear(
            estado=EstadoReserva.APROBADA,
            revisado_por=self.aprobador,
        )
        rechazada = self.crear(
            estado=EstadoReserva.RECHAZADA,
            fecha=self.fecha_alterna,
        )

        with self.assertRaises(ValidationError):
            aprobar_reserva(reserva=aprobada, actor=self.aprobador)
        with self.assertRaises(ValidationError):
            rechazar_reserva(
                reserva=aprobada,
                actor=self.aprobador,
                motivo="Intento inválido",
            )
        with self.assertRaises(ValidationError):
            cancelar_reserva(reserva=rechazada, actor=self.solicitante)

        self.assertFalse(
            HistorialReserva.objects.filter(
                reserva__in=[aprobada, rechazada]
            ).exists()
        )


class HistorialAtomicidadTests(HistorialBaseTests):
    """REQ-HIS-002: estado e historial comparten la misma transacción."""

    def test_req_his_002_fallo_historial_revierte_cancelacion(self):
        reserva = self.crear()
        antes = HistorialReserva.objects.count()

        with mock.patch.object(
            HistorialReserva.objects,
            "create",
            side_effect=IntegrityError("fallo de historial"),
        ):
            with self.assertRaises(IntegrityError):
                cancelar_reserva(reserva=reserva, actor=self.solicitante)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(HistorialReserva.objects.count(), antes)

    def test_req_his_002_fallo_historial_revierte_creacion(self):
        datos = datos_solicitud(
            fecha=self.fecha,
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
            motivo="Creación atómica",
        )
        antes_reservas = Reserva.objects.count()
        antes_historial = HistorialReserva.objects.count()

        with mock.patch.object(
            HistorialReserva.objects,
            "create",
            side_effect=IntegrityError("fallo de historial"),
        ):
            with self.assertRaises(IntegrityError):
                crear_solicitud(
                    espacio=self.espacio,
                    solicitante=self.solicitante,
                    **datos,
                )

        self.assertEqual(Reserva.objects.count(), antes_reservas)
        self.assertEqual(HistorialReserva.objects.count(), antes_historial)

    def test_req_his_002_fallo_historial_revierte_aprobacion(self):
        reserva = self.crear()
        antes = HistorialReserva.objects.count()

        with mock.patch.object(
            HistorialReserva.objects,
            "create",
            side_effect=IntegrityError("fallo de historial"),
        ):
            with self.assertRaises(IntegrityError):
                aprobar_reserva(reserva=reserva, actor=self.aprobador)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertIsNone(reserva.revisado_por)
        self.assertEqual(HistorialReserva.objects.count(), antes)

    def test_req_his_002_excepcion_de_registrar_historial_atraviesa_el_atomic(
        self,
    ):
        reserva = self.crear()

        with mock.patch(
            "reservations.services._registrar_historial",
            side_effect=RuntimeError("fallo de auditoría"),
        ):
            with self.assertRaises(RuntimeError):
                cancelar_reserva(reserva=reserva, actor=self.solicitante)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertFalse(
            HistorialReserva.objects.filter(reserva=reserva).exists()
        )


class HistorialTransaccionTests(TransactionTestCase):
    """REQ-HIS-002: el helper exige una transacción activa."""

    def setUp(self):
        self.espacio = crear_espacio(nombre="Espacio transacción historial")
        self.solicitante = crear_usuario(rol=Rol.SOLICITANTE)
        self.reserva = crear_reserva(
            espacio=self.espacio,
            solicitante=self.solicitante,
        )

    def test_req_his_002_registrar_historial_fuera_de_transaccion_falla(self):
        with self.assertRaises(RuntimeError):
            _registrar_historial(
                reserva=self.reserva,
                estado_anterior=None,
                estado_nuevo=EstadoReserva.PENDIENTE,
                actor=self.solicitante,
            )

        self.assertFalse(
            HistorialReserva.objects.filter(reserva=self.reserva).exists()
        )

    def test_req_his_002_registrar_historial_dentro_de_transaccion_inserta(self):
        with transaction.atomic():
            evento = _registrar_historial(
                reserva=self.reserva,
                estado_anterior=None,
                estado_nuevo=EstadoReserva.PENDIENTE,
                actor=self.solicitante,
            )

        self.assertEqual(evento.estado_nuevo, EstadoReserva.PENDIENTE)
        self.assertTrue(
            HistorialReserva.objects.filter(pk=evento.pk).exists()
        )


class HistorialInmutabilidadTests(HistorialBaseTests):
    """REQ-HIS-003: el historial no se modifica ni se elimina."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.reserva = crear_reserva(
            espacio=cls.espacio,
            solicitante=cls.solicitante,
        )
        cls.evento = crear_historial(
            reserva=cls.reserva,
            actor=cls.solicitante,
            estado_anterior=None,
            estado_nuevo=EstadoReserva.PENDIENTE,
            observacion="Observación original",
        )
        cls.superusuario = crear_usuario(
            rol=Rol.ADMINISTRADOR,
            username="hist_superusuario",
            is_staff=True,
            is_superuser=True,
        )

    def test_req_his_003_modificar_registro_existente_falla(self):
        self.evento.observacion = "Intento de cambio"

        with self.assertRaises(ValidationError):
            self.evento.save()

        guardado = HistorialReserva.objects.get(pk=self.evento.pk)
        self.assertEqual(guardado.observacion, "Observación original")

    def test_req_his_003_eliminar_registro_individual_falla(self):
        with self.assertRaises(ValidationError):
            self.evento.delete()

        self.assertTrue(
            HistorialReserva.objects.filter(pk=self.evento.pk).exists()
        )

    def test_req_his_003_eliminar_registros_masivamente_falla(self):
        with self.assertRaises(ValidationError):
            HistorialReserva.objects.all().delete()

        self.assertTrue(
            HistorialReserva.objects.filter(pk=self.evento.pk).exists()
        )

    def test_req_his_003_update_masivo_falla(self):
        with self.assertRaises(ValidationError):
            HistorialReserva.objects.filter(pk=self.evento.pk).update(
                observacion="Intento masivo"
            )

        guardado = HistorialReserva.objects.get(pk=self.evento.pk)
        self.assertEqual(guardado.observacion, "Observación original")

    def test_req_his_003_bulk_update_falla(self):
        self.evento.observacion = "Intento bulk"

        with self.assertRaises(ValidationError):
            HistorialReserva.objects.bulk_update(
                [self.evento],
                ["observacion"],
            )

        guardado = HistorialReserva.objects.get(pk=self.evento.pk)
        self.assertEqual(guardado.observacion, "Observación original")

    def test_req_his_003_insercion_nueva_sigue_permitida(self):
        evento = HistorialReserva.objects.create(
            reserva=self.reserva,
            estado_anterior=EstadoReserva.PENDIENTE,
            estado_nuevo=EstadoReserva.APROBADA,
            actor=self.aprobador,
        )

        self.assertTrue(
            HistorialReserva.objects.filter(pk=evento.pk).exists()
        )

    def test_req_his_003_admin_es_solo_lectura(self):
        modelo_admin = admin.site._registry[HistorialReserva]

        self.assertFalse(modelo_admin.has_add_permission(None))
        self.assertFalse(modelo_admin.has_change_permission(None))
        self.assertFalse(modelo_admin.has_delete_permission(None))
        self.assertTrue(modelo_admin.has_view_permission(None))
        self.assertEqual(
            set(modelo_admin.readonly_fields),
            {campo.name for campo in HistorialReserva._meta.fields},
        )

        self.client.force_login(self.superusuario)
        listado = self.client.get(
            reverse("admin:reservations_historialreserva_changelist")
        )
        detalle = self.client.get(
            reverse(
                "admin:reservations_historialreserva_change",
                args=[self.evento.pk],
            )
        )
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(detalle.status_code, 200)


class HistorialVisibilidadTests(HistorialBaseTests):
    """REQ-HIS-004: alcance del historial por usuario y detalle."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.propia = crear_reserva(
            espacio=cls.espacio,
            solicitante=cls.solicitante,
            motivo="Reserva propia de historial",
        )
        cls.ajena = crear_reserva(
            espacio=cls.otro_espacio,
            solicitante=cls.otro_solicitante,
            motivo="Reserva ajena de historial",
        )
        cls.del_aprobador = crear_reserva(
            espacio=cls.espacio,
            solicitante=cls.aprobador,
            motivo="Reserva del aprobador",
        )
        cls.evento_propio = crear_historial(
            reserva=cls.propia,
            actor=cls.solicitante,
            estado_anterior=None,
            estado_nuevo=EstadoReserva.PENDIENTE,
            observacion="Evento propio",
        )
        cls.evento_ajeno = crear_historial(
            reserva=cls.ajena,
            actor=cls.otro_solicitante,
            estado_anterior=None,
            estado_nuevo=EstadoReserva.PENDIENTE,
            observacion="Evento ajeno",
        )
        cls.evento_aprobador = crear_historial(
            reserva=cls.del_aprobador,
            actor=cls.aprobador,
            estado_anterior=None,
            estado_nuevo=EstadoReserva.PENDIENTE,
            observacion="Evento del aprobador",
        )

    def historial(self, respuesta):
        return list(respuesta.context["historial"])

    def test_req_his_004_solicitante_solo_ve_sus_eventos(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(reverse("reservations:historial"))

        eventos = self.historial(respuesta)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([evento.pk for evento in eventos], [
            self.evento_propio.pk,
        ])
        self.assertNotIn(self.evento_ajeno, eventos)
        self.assertNotIn(self.evento_aprobador, eventos)

    def test_req_his_004_administrador_ve_todos_los_eventos(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.get(reverse("reservations:historial"))

        eventos = self.historial(respuesta)
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(self.evento_propio, eventos)
        self.assertIn(self.evento_ajeno, eventos)
        self.assertIn(self.evento_aprobador, eventos)

    def test_req_his_004_filtro_por_espacio_no_amplia_el_alcance(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:historial"),
            {"espacio": self.espacio.pk},
        )

        eventos = self.historial(respuesta)
        self.assertIn(self.evento_propio, eventos)
        self.assertNotIn(self.evento_aprobador, eventos)
        self.assertNotIn(self.evento_ajeno, eventos)

    def test_req_his_004_aprobador_no_ve_historial_ajeno(self):
        self.client.force_login(self.aprobador)

        detalle = self.client.get(
            reverse("reservations:solicitud_detalle", args=[self.propia.pk])
        )
        listado = self.client.get(reverse("reservations:historial"))

        self.assertEqual(detalle.status_code, 200)
        self.assertNotContains(detalle, "Historial de cambios")
        self.assertNotIn(self.evento_propio, self.historial(listado))
        self.assertNotIn(self.evento_ajeno, self.historial(listado))
        self.assertIn(self.evento_aprobador, self.historial(listado))

    def test_req_his_004_solicitante_y_administrador_ven_el_detalle(self):
        momento_1 = timezone.now() - timedelta(hours=2)
        momento_2 = timezone.now() - timedelta(hours=1)
        crear_historial(
            reserva=self.propia,
            actor=self.solicitante,
            estado_anterior=EstadoReserva.PENDIENTE,
            estado_nuevo=EstadoReserva.APROBADA,
            observacion="Aprobación visible",
            fecha_evento=momento_1,
        )
        crear_historial(
            reserva=self.propia,
            actor=self.solicitante,
            estado_anterior=EstadoReserva.APROBADA,
            estado_nuevo=EstadoReserva.CANCELADA,
            observacion="Cancelación visible",
            fecha_evento=momento_2,
        )
        ruta = reverse(
            "reservations:solicitud_detalle",
            args=[self.propia.pk],
        )

        self.client.force_login(self.solicitante)
        detalle_solicitante = self.client.get(ruta)

        self.assertContains(detalle_solicitante, "Historial de cambios")
        self.assertContains(detalle_solicitante, "Creación")
        self.assertContains(detalle_solicitante, "Pendiente")
        self.assertContains(detalle_solicitante, "Aprobada")
        self.assertContains(detalle_solicitante, "Cancelada")
        self.assertContains(detalle_solicitante, "Aprobación visible")
        self.assertContains(detalle_solicitante, "Cancelación visible")
        self.assertContains(detalle_solicitante, "Sofía Solicitante")
        fechas = [
            evento.fecha_evento
            for evento in detalle_solicitante.context["historial"]
        ]
        self.assertEqual(fechas, sorted(fechas))

        self.client.force_login(self.administrador)
        detalle_admin = self.client.get(ruta)
        self.assertContains(detalle_admin, "Historial de cambios")

    def test_req_his_004_anonimo_redirigido_al_login_con_next(self):
        ruta = reverse("reservations:historial")

        respuesta = self.client.get(ruta)

        self.assertEqual(respuesta.status_code, 302)
        destino = urlparse(respuesta["Location"])
        self.assertEqual(destino.path, reverse("accounts:login"))
        self.assertEqual(parse_qs(destino.query)["next"], [ruta])


class HistorialFiltrosTests(HistorialBaseTests):
    """REQ-HIS-005: filtros combinables y valores inválidos ignorados."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.fecha_a = timezone.localdate() - timedelta(days=2)
        cls.fecha_b = timezone.localdate() - timedelta(days=1)
        cls.reserva_a = crear_reserva(
            espacio=cls.espacio,
            solicitante=cls.solicitante,
            motivo="Reserva A",
        )
        cls.reserva_b = crear_reserva(
            espacio=cls.otro_espacio,
            solicitante=cls.solicitante,
            motivo="Reserva B",
        )
        cls.reserva_otro = crear_reserva(
            espacio=cls.otro_espacio,
            solicitante=cls.otro_solicitante,
            motivo="Reserva de otro usuario",
        )
        zona = timezone.get_current_timezone()
        cls.evento_pendiente = crear_historial(
            reserva=cls.reserva_a,
            actor=cls.solicitante,
            estado_nuevo=EstadoReserva.PENDIENTE,
            fecha_evento=timezone.make_aware(
                datetime.combine(cls.fecha_a, time(9, 0)),
                zona,
            ),
        )
        cls.evento_aprobado = crear_historial(
            reserva=cls.reserva_a,
            actor=cls.solicitante,
            estado_anterior=EstadoReserva.PENDIENTE,
            estado_nuevo=EstadoReserva.APROBADA,
            fecha_evento=timezone.make_aware(
                datetime.combine(cls.fecha_a, time(10, 0)),
                zona,
            ),
        )
        cls.evento_cancelado = crear_historial(
            reserva=cls.reserva_a,
            actor=cls.solicitante,
            estado_anterior=EstadoReserva.APROBADA,
            estado_nuevo=EstadoReserva.CANCELADA,
            fecha_evento=timezone.make_aware(
                datetime.combine(cls.fecha_b, time(11, 0)),
                zona,
            ),
        )
        cls.evento_aprobado_b = crear_historial(
            reserva=cls.reserva_b,
            actor=cls.solicitante,
            estado_anterior=EstadoReserva.PENDIENTE,
            estado_nuevo=EstadoReserva.APROBADA,
            fecha_evento=timezone.make_aware(
                datetime.combine(cls.fecha_a, time(12, 0)),
                zona,
            ),
        )
        cls.evento_ajeno = crear_historial(
            reserva=cls.reserva_otro,
            actor=cls.otro_solicitante,
            estado_anterior=EstadoReserva.PENDIENTE,
            estado_nuevo=EstadoReserva.APROBADA,
            fecha_evento=timezone.make_aware(
                datetime.combine(cls.fecha_a, time(13, 0)),
                zona,
            ),
        )

    def historial(self, respuesta):
        return list(respuesta.context["historial"])

    def test_req_his_005_filtro_por_estado(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:historial"),
            {"estado": EstadoReserva.APROBADA},
        )

        eventos = self.historial(respuesta)
        self.assertEqual(
            {evento.pk for evento in eventos},
            {self.evento_aprobado.pk, self.evento_aprobado_b.pk},
        )
        self.assertTrue(
            all(
                evento.estado_nuevo == EstadoReserva.APROBADA
                for evento in eventos
            )
        )

    def test_req_his_005_filtro_por_fecha_local(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:historial"),
            {"fecha": self.fecha_a.isoformat()},
        )

        eventos = self.historial(respuesta)
        self.assertIn(self.evento_pendiente, eventos)
        self.assertIn(self.evento_aprobado, eventos)
        self.assertIn(self.evento_aprobado_b, eventos)
        self.assertNotIn(self.evento_cancelado, eventos)

    def test_req_his_005_filtro_por_espacio(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:historial"),
            {"espacio": self.espacio.pk},
        )

        eventos = self.historial(respuesta)
        self.assertEqual(
            {evento.pk for evento in eventos},
            {
                self.evento_pendiente.pk,
                self.evento_aprobado.pk,
                self.evento_cancelado.pk,
            },
        )

    def test_req_his_005_filtros_combinados_y_sticky(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:historial"),
            {
                "estado": EstadoReserva.APROBADA,
                "fecha": self.fecha_a.isoformat(),
                "espacio": self.espacio.pk,
            },
        )

        eventos = self.historial(respuesta)
        self.assertEqual([evento.pk for evento in eventos], [
            self.evento_aprobado.pk,
        ])
        self.assertEqual(
            respuesta.context["filtros"],
            {
                "estado": EstadoReserva.APROBADA,
                "fecha": self.fecha_a.isoformat(),
                "espacio": self.espacio.pk,
            },
        )
        self.assertContains(
            respuesta,
            f'value="{self.fecha_a.isoformat()}"',
        )
        self.assertContains(respuesta, 'value="APROBADA" selected')

    def test_req_his_005_valores_invalidos_se_ignoran_sin_ampliar_alcance(
        self,
    ):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:historial"),
            {
                "estado": "NOEXISTE",
                "fecha": "no-es-fecha",
                "espacio": "no-es-id",
            },
        )

        eventos = self.historial(respuesta)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.context["filtros"],
            {"estado": "", "fecha": "", "espacio": ""},
        )
        self.assertIn(self.evento_pendiente, eventos)
        self.assertIn(self.evento_aprobado, eventos)
        self.assertIn(self.evento_cancelado, eventos)
        self.assertIn(self.evento_aprobado_b, eventos)
        self.assertNotIn(self.evento_ajeno, eventos)

    def test_req_his_005_administrador_filtra_sobre_todos_los_eventos(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.get(
            reverse("reservations:historial"),
            {"espacio": self.otro_espacio.pk},
        )

        eventos = self.historial(respuesta)
        self.assertIn(self.evento_aprobado_b, eventos)
        self.assertIn(self.evento_ajeno, eventos)
        self.assertNotIn(self.evento_pendiente, eventos)

    def test_req_his_005_estado_vacio(self):
        self.client.force_login(self.solicitante)
        fecha_sin_eventos = timezone.localdate() - timedelta(days=10)

        respuesta = self.client.get(
            reverse("reservations:historial"),
            {"fecha": fecha_sin_eventos.isoformat()},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.historial(respuesta), [])
        self.assertContains(
            respuesta,
            "No hay eventos de historial para mostrar.",
        )
