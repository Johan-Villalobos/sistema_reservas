"""Pruebas de las reglas de negocio de reservas, sin cliente HTTP.

Cubre REQ-SOL-001 a REQ-SOL-007 y REQ-SOL-011, y las reglas de disponibilidad
REQ-DIS-003, REQ-DIS-006, REQ-DIS-007 y REQ-DIS-009.
"""

from datetime import date, datetime, time, timedelta

from django.core.exceptions import (
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.roles import Rol
from reservations.models import EstadoReserva, Reserva
from reservations.services import (
    aprobar_reserva,
    crear_solicitud,
    obtener_horario_operativo,
    validar_solicitud,
)
from reservations.tests.utils import (
    crear_espacio,
    crear_reserva,
    crear_reserva_aprobada,
    crear_usuario,
    datos_solicitud,
)


class ServicioReservaTests(TestCase):
    """Creación transaccional, validaciones y horario configurable."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio()
        cls.solicitante = crear_usuario()
        cls.datos = datos_solicitud()

    def crear(self, **cambios):
        datos = {**self.datos, **cambios}
        return crear_solicitud(
            espacio=datos.pop("espacio", self.espacio),
            solicitante=datos.pop("solicitante", self.solicitante),
            **datos,
        )

    def test_req_sol_001_creacion_valida_queda_pendiente(self):
        reserva = self.crear()

        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(reserva.solicitante_id, self.solicitante.pk)
        self.assertIsNotNone(reserva.creado_en)
        self.assertTrue(Reserva.objects.filter(pk=reserva.pk).exists())

    def test_req_sol_001_crear_con_cada_rol(self):
        for indice, rol in enumerate(Rol):
            with self.subTest(rol=rol):
                usuario = crear_usuario(rol=rol)
                reserva = self.crear(
                    solicitante=usuario,
                    motivo=f"Reserva de {rol}",
                )

                self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
                self.assertEqual(reserva.solicitante_id, usuario.pk)

    def test_req_sol_002_estado_enviado_al_servicio_se_ignora(self):
        antes = Reserva.objects.count()

        with self.assertRaises(TypeError):
            self.crear(estado=EstadoReserva.APROBADA)

        self.assertEqual(Reserva.objects.count(), antes)

    def test_req_sol_003_hora_fin_igual_es_rechazada(self):
        antes = Reserva.objects.count()

        with self.assertRaises(ValidationError) as contexto:
            self.crear(hora_inicio=time(10, 0), hora_fin=time(10, 0))

        self.assertIn("hora_fin", contexto.exception.message_dict)
        self.assertEqual(Reserva.objects.count(), antes)

    def test_req_sol_003_hora_fin_anterior_es_rechazada(self):
        with self.assertRaises(ValidationError) as contexto:
            self.crear(hora_inicio=time(12, 0), hora_fin=time(11, 0))

        self.assertIn("hora_fin", contexto.exception.message_dict)

    def test_req_sol_004_fecha_de_ayer_es_rechazada(self):
        with self.assertRaises(ValidationError) as contexto:
            self.crear(fecha=date.today() - timedelta(days=1))

        self.assertIn("hora_inicio", contexto.exception.message_dict)

    def test_req_sol_004_hora_transcurrida_hoy_con_ahora_inyectado(self):
        zona = timezone.get_current_timezone()
        ahora = timezone.make_aware(datetime(2030, 1, 2, 12, 0), zona)

        with self.assertRaises(ValidationError) as contexto:
            validar_solicitud(
                espacio=self.espacio,
                fecha=date(2030, 1, 2),
                hora_inicio=time(11, 0),
                hora_fin=time(12, 0),
                motivo="Hora ya transcurrida",
                ahora=ahora,
            )

        self.assertIn("hora_inicio", contexto.exception.message_dict)

    def test_req_sol_004_fecha_futura_es_aceptada(self):
        reserva = self.crear()

        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)

    def test_req_sol_005_espacio_inactivo_es_rechazado(self):
        inactivo = crear_espacio(nombre="Inactivo Servicio", activo=False)
        antes = Reserva.objects.count()

        with self.assertRaises(ValidationError) as contexto:
            self.crear(espacio=inactivo)

        self.assertIn("espacio", contexto.exception.message_dict)
        self.assertEqual(Reserva.objects.count(), antes)

    def test_req_sol_005_crear_reconsulta_el_estado_activo(self):
        # La instancia en memoria sigue activa, pero en base ya no lo está.
        instancia = self.espacio
        self.espacio.__class__.objects.filter(pk=instancia.pk).update(
            activo=False
        )

        with self.assertRaises(ValidationError) as contexto:
            self.crear(espacio=instancia)

        self.assertIn("espacio", contexto.exception.message_dict)

    def test_req_sol_006_motivo_vacio_es_rechazado(self):
        for motivo in ("", "   "):
            with self.subTest(motivo=repr(motivo)):
                with self.assertRaises(ValidationError) as contexto:
                    self.crear(motivo=motivo)
                self.assertIn("motivo", contexto.exception.message_dict)

    def test_req_sol_006_motivo_de_255_caracteres_es_aceptado(self):
        reserva = self.crear(motivo="x" * 255)

        self.assertEqual(len(reserva.motivo), 255)

    def test_req_sol_006_motivo_de_256_caracteres_es_rechazado(self):
        with self.assertRaises(ValidationError) as contexto:
            self.crear(motivo="x" * 256)

        self.assertIn("motivo", contexto.exception.message_dict)

    def test_req_sol_007_limites_del_horario_operativo(self):
        with self.assertRaises(ValidationError) as temprano:
            validar_solicitud(
                espacio=self.espacio,
                fecha=self.datos["fecha"],
                hora_inicio=time(5, 59),
                hora_fin=time(7, 0),
                motivo="Antes de abrir",
            )
        self.assertIn("hora_inicio", temprano.exception.message_dict)

        apertura = self.crear(
            hora_inicio=time(6, 0),
            hora_fin=time(7, 0),
            motivo="Apertura",
        )
        cierre = self.crear(
            hora_inicio=time(21, 0),
            hora_fin=time(22, 0),
            motivo="Cierre",
        )
        self.assertEqual(apertura.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(cierre.estado, EstadoReserva.PENDIENTE)

        with self.assertRaises(ValidationError) as tarde:
            validar_solicitud(
                espacio=self.espacio,
                fecha=self.datos["fecha"],
                hora_inicio=time(21, 0),
                hora_fin=time(22, 1),
                motivo="Después de cerrar",
            )
        self.assertIn("hora_fin", tarde.exception.message_dict)

    @override_settings(
        HORARIO_OPERATIVO_INICIO="08:00",
        HORARIO_OPERATIVO_FIN="18:00",
    )
    def test_req_sol_007_horario_operativo_configurable(self):
        with self.assertRaises(ValidationError) as antes:
            self.crear(
                hora_inicio=time(7, 0),
                hora_fin=time(9, 0),
                motivo="Antes de las 08:00",
            )
        self.assertIn("hora_inicio", antes.exception.message_dict)

        with self.assertRaises(ValidationError) as despues:
            self.crear(
                hora_inicio=time(17, 0),
                hora_fin=time(19, 0),
                motivo="Después de las 18:00",
            )
        self.assertIn("hora_fin", despues.exception.message_dict)

        reserva = self.crear(
            hora_inicio=time(8, 0),
            hora_fin=time(18, 0),
            motivo="Franja completa",
        )
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)

    @override_settings(HORARIO_OPERATIVO_INICIO="NOESUNAHORA")
    def test_req_sol_007_configuracion_invalida_lanza_excepcion(self):
        with self.assertRaises(ImproperlyConfigured):
            obtener_horario_operativo()

    def test_req_sol_011_crear_solo_escribe_estado_pendiente(self):
        reserva = self.crear()

        self.assertEqual(
            Reserva._meta.get_field("estado").default,
            EstadoReserva.PENDIENTE,
        )
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)


class DisponibilidadCreacionYAprobacionTests(TestCase):
    """Creación y aprobación comparten la regla de cruces y su mensaje."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio(nombre="Espacio de disponibilidad")
        cls.solicitante = crear_usuario()
        cls.aprobador = crear_usuario(rol=Rol.APROBADOR)
        cls.administrador = crear_usuario(rol=Rol.ADMINISTRADOR)
        cls.fecha = date.today() + timedelta(days=30)

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
        return crear_reserva(estado=EstadoReserva.PENDIENTE, **datos)

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

    # REQ-DIS-003 y REQ-DIS-009: creación.

    def test_req_dis_003_crear_rechaza_cruce_sin_crear_fila(self):
        self.crear_aprobada()
        antes = Reserva.objects.count()

        with self.assertRaises(ValidationError) as contexto:
            crear_solicitud(
                espacio=self.espacio,
                solicitante=self.solicitante,
                fecha=self.fecha,
                hora_inicio=time(11, 0),
                hora_fin=time(13, 0),
                motivo="Intento de cruce",
            )

        self.assertIn("hora_inicio", contexto.exception.message_dict)
        self.assertEqual(Reserva.objects.count(), antes)

    def test_req_dis_003_mensaje_incluye_espacio_fecha_y_franja(self):
        self.crear_aprobada()

        with self.assertRaises(ValidationError) as contexto:
            crear_solicitud(
                espacio=self.espacio,
                solicitante=self.solicitante,
                fecha=self.fecha,
                hora_inicio=time(11, 0),
                hora_fin=time(13, 0),
                motivo="Intento de cruce",
            )

        mensaje = contexto.exception.message_dict["hora_inicio"][0]
        self.assertIn(self.espacio.nombre, mensaje)
        self.assertIn(str(self.fecha), mensaje)
        self.assertIn("10:00", mensaje)
        self.assertIn("12:00", mensaje)

    def test_req_dis_009_creacion_y_aprobacion_comparten_mensaje(self):
        self.crear_aprobada()

        with self.assertRaises(ValidationError) as creacion:
            crear_solicitud(
                espacio=self.espacio,
                solicitante=self.solicitante,
                fecha=self.fecha,
                hora_inicio=time(11, 0),
                hora_fin=time(12, 0),
                motivo="Cruce al crear",
            )

        pendiente = self.crear_pendiente(
            hora_inicio=time(11, 0),
            hora_fin=time(12, 0),
        )
        with self.assertRaises(ValidationError) as aprobacion:
            aprobar_reserva(reserva=pendiente, actor=self.aprobador)

        self.assertEqual(
            creacion.exception.message_dict["hora_inicio"],
            aprobacion.exception.message_dict["hora_inicio"],
        )

    # REQ-DIS-006 y REQ-DIS-007: aprobación.

    def test_req_dis_006_aprobacion_con_conflicto_deja_pendiente(self):
        self.crear_aprobada(
            hora_inicio=time(11, 0),
            hora_fin=time(13, 0),
        )
        pendiente = self.crear_pendiente()

        with self.assertRaises(ValidationError) as contexto:
            aprobar_reserva(reserva=pendiente, actor=self.aprobador)

        self.assertIn("hora_inicio", contexto.exception.message_dict)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_dis_006_conflicto_creado_despues_impide_aprobar(self):
        pendiente = self.crear_pendiente()
        self.crear_aprobada(
            hora_inicio=time(10, 0),
            hora_fin=time(11, 0),
        )

        with self.assertRaises(ValidationError):
            aprobar_reserva(reserva=pendiente, actor=self.aprobador)

        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)

    def test_req_dis_007_dos_pendientes_cruzadas_la_segunda_falla(self):
        primera = self.crear_pendiente(
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
        )
        segunda = self.crear_pendiente(
            hora_inicio=time(11, 0),
            hora_fin=time(13, 0),
        )

        aprobar_reserva(reserva=primera, actor=self.aprobador)
        primera.refresh_from_db()
        self.assertEqual(primera.estado, EstadoReserva.APROBADA)

        with self.assertRaises(ValidationError) as contexto:
            aprobar_reserva(reserva=segunda, actor=self.aprobador)

        self.assertIn("hora_inicio", contexto.exception.message_dict)
        segunda.refresh_from_db()
        self.assertEqual(segunda.estado, EstadoReserva.PENDIENTE)

    def test_req_dis_006_solicitud_sin_conflicto_se_aprueba(self):
        pendiente = self.crear_pendiente()

        aprobada = aprobar_reserva(
            reserva=pendiente,
            actor=self.aprobador,
        )

        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)
        self.assertEqual(
            Reserva.objects.get(pk=pendiente.pk).estado,
            EstadoReserva.APROBADA,
        )

    def test_req_dis_006_administrador_puede_aprobar(self):
        pendiente = self.crear_pendiente()

        aprobada = aprobar_reserva(
            reserva=pendiente,
            actor=self.administrador,
        )

        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)

    def test_req_dis_006_reserva_no_pendiente_no_se_aprueba(self):
        aprobada = self.crear_aprobada()

        with self.assertRaises(ValidationError) as contexto:
            aprobar_reserva(reserva=aprobada, actor=self.aprobador)

        self.assertIn("estado", contexto.exception.message_dict)
        aprobada.refresh_from_db()
        self.assertEqual(aprobada.estado, EstadoReserva.APROBADA)

    def test_req_dis_006_actor_sin_rol_no_puede_aprobar(self):
        pendiente = self.crear_pendiente()

        with self.assertRaises(PermissionDenied):
            aprobar_reserva(reserva=pendiente, actor=self.solicitante)

        pendiente.refresh_from_db()
        self.assertEqual(pendiente.estado, EstadoReserva.PENDIENTE)
