"""Pruebas de las vistas de solicitudes de reserva.

Cubre REQ-SOL-001 a REQ-SOL-009 y REQ-DIS-008 desde el cliente HTTP.
"""

from datetime import date, time, timedelta
from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from django.urls import reverse

from accounts.roles import Rol
from reservations.models import EstadoReserva, Reserva
from reservations.services import aprobar_reserva
from reservations.tests.utils import (
    crear_espacio,
    crear_reserva,
    crear_reserva_aprobada,
    crear_usuario,
    datos_solicitud,
)


class SolicitudViewsTests(TestCase):
    """Creación, listado propio y visibilidad restringida del detalle."""

    @classmethod
    def setUpTestData(cls):
        cls.activo = crear_espacio(nombre="Espacio Activo Visible")
        cls.inactivo = crear_espacio(
            nombre="Espacio Inactivo Oculto",
            activo=False,
        )
        cls.solicitante = crear_usuario(rol=Rol.SOLICITANTE)
        cls.aprobador = crear_usuario(rol=Rol.APROBADOR)
        cls.administrador = crear_usuario(rol=Rol.ADMINISTRADOR)
        cls.otro_solicitante = crear_usuario(rol=Rol.SOLICITANTE)

    def datos_post(self, **cambios):
        datos = datos_solicitud()
        datos = {
            "espacio": self.activo.pk,
            "fecha": datos["fecha"].isoformat(),
            "hora_inicio": datos["hora_inicio"].strftime("%H:%M"),
            "hora_fin": datos["hora_fin"].strftime("%H:%M"),
            "motivo": datos["motivo"],
        }
        datos.update(cambios)
        return datos

    def crear_reserva(self, solicitante=None, **cambios):
        datos = datos_solicitud()
        datos.update(cambios)
        return Reserva.objects.create(
            espacio=datos.pop("espacio", self.activo),
            solicitante=solicitante or self.solicitante,
            **datos,
        )

    def assert_redirige_al_login(self, respuesta, ruta):
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta["Location"],
            f"{reverse('accounts:login')}?next={ruta}",
        )

    # REQ-SOL-001: creación por cualquier rol autenticado.

    def test_req_sol_001_solicitante_crea_solicitud_pendiente(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(),
        )

        reserva = Reserva.objects.get()
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta["Location"],
            reverse("reservations:solicitud_detalle", args=[reserva.pk]),
        )
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(reserva.solicitante_id, self.solicitante.pk)

    def test_req_sol_001_aprobador_crea_solicitud_pendiente(self):
        self.client.force_login(self.aprobador)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(),
        )

        self.assertEqual(respuesta.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(reserva.solicitante_id, self.aprobador.pk)

    def test_req_sol_001_administrador_crea_solicitud_pendiente(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(),
        )

        self.assertEqual(respuesta.status_code, 302)
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(reserva.solicitante_id, self.administrador.pk)

    def test_req_sol_001_solicitante_enviado_por_cliente_se_ignora(self):
        self.client.force_login(self.solicitante)

        self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(solicitante=self.otro_solicitante.pk),
        )

        reserva = Reserva.objects.get()
        self.assertEqual(reserva.solicitante_id, self.solicitante.pk)

    def test_req_sol_001_anonimo_es_redirigido_al_login(self):
        ruta = reverse("reservations:solicitud_crear")

        respuesta = self.client.get(ruta)

        self.assert_redirige_al_login(respuesta, ruta)

    # REQ-SOL-002: estado inicial no manipulable.

    def test_req_sol_002_estado_aprobada_enviado_por_cliente_se_ignora(self):
        self.client.force_login(self.solicitante)

        self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(estado=EstadoReserva.APROBADA),
        )

        reserva = Reserva.objects.get()
        self.assertEqual(reserva.estado, EstadoReserva.PENDIENTE)
        self.assertIsNotNone(reserva.creado_en)

    # REQ-SOL-003: franja coherente y en un solo día.

    def test_req_sol_003_hora_fin_igual_muestra_error_y_no_crea(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(hora_inicio="10:00", hora_fin="10:00"),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("hora_fin", respuesta.context["form"].errors)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_req_sol_003_hora_fin_menor_muestra_error_y_no_crea(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(hora_inicio="12:00", hora_fin="11:00"),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("hora_fin", respuesta.context["form"].errors)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_req_sol_003_formulario_sin_fecha_fin_y_detalle_una_fecha(self):
        self.client.force_login(self.solicitante)
        formulario = self.client.get(reverse("reservations:solicitud_crear"))

        self.assertNotContains(formulario, "fecha_fin")

        reserva = self.crear_reserva()
        detalle = self.client.get(
            reverse("reservations:solicitud_detalle", args=[reserva.pk])
        )
        self.assertContains(detalle, reserva.fecha.strftime("%d/%m/%Y"))

    # REQ-SOL-004: rechazo del pasado.

    def test_req_sol_004_fecha_pasada_se_rechaza(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(fecha="2020-01-01"),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("hora_inicio", respuesta.context["form"].errors)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_req_sol_004_solicitud_futura_se_acepta(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(),
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Reserva.objects.get().estado, EstadoReserva.PENDIENTE)

    # REQ-SOL-005: espacios inactivos.

    def test_req_sol_005_espacio_inactivo_enviado_manualmente_se_rechaza(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(espacio=self.inactivo.pk),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("espacio", respuesta.context["form"].errors)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_req_sol_005_selector_solo_muestra_espacios_activos(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(reverse("reservations:solicitud_crear"))

        self.assertContains(respuesta, self.activo.nombre)
        self.assertNotContains(respuesta, self.inactivo.nombre)

    # REQ-SOL-006: motivo obligatorio y máximo 255.

    def test_req_sol_006_motivo_vacio_se_rechaza(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(motivo=""),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("motivo", respuesta.context["form"].errors)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_req_sol_006_motivo_de_255_caracteres_se_acepta(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(motivo="x" * 255),
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(len(Reserva.objects.get().motivo), 255)

    def test_req_sol_006_motivo_de_256_caracteres_se_rechaza(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(motivo="x" * 256),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("motivo", respuesta.context["form"].errors)
        self.assertEqual(Reserva.objects.count(), 0)

    # REQ-SOL-007: horario operativo.

    def test_req_sol_007_fuera_del_horario_se_rechaza(self):
        self.client.force_login(self.solicitante)

        antes = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(hora_inicio="05:59", hora_fin="07:00"),
        )
        despues = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(hora_inicio="21:00", hora_fin="22:01"),
        )

        self.assertIn("hora_inicio", antes.context["form"].errors)
        self.assertIn("hora_fin", despues.context["form"].errors)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_req_sol_007_limites_del_horario_se_aceptan(self):
        self.client.force_login(self.solicitante)

        respuesta = self.client.post(
            reverse("reservations:solicitud_crear"),
            self.datos_post(hora_inicio="06:00", hora_fin="22:00"),
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Reserva.objects.get().estado, EstadoReserva.PENDIENTE)

    # REQ-SOL-008: listado propio.

    def test_req_sol_008_listado_muestra_solo_solicitudes_propias(self):
        propia = self.crear_reserva(motivo="Propia")
        ajena = self.crear_reserva(
            solicitante=self.otro_solicitante,
            motivo="Ajena",
        )
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(reverse("reservations:solicitud_lista"))

        solicitudes = list(respuesta.context["solicitudes"])
        self.assertIn(propia, solicitudes)
        self.assertNotIn(ajena, solicitudes)

    def test_req_sol_008_listado_muestra_franja_estado_y_enlace(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(reverse("reservations:solicitud_lista"))

        self.assertContains(respuesta, reserva.espacio.nombre)
        self.assertContains(respuesta, reserva.fecha.strftime("%d/%m/%Y"))
        self.assertContains(respuesta, "10:00")
        self.assertContains(respuesta, "11:00")
        self.assertContains(respuesta, "Pendiente")
        self.assertContains(
            respuesta,
            reverse("reservations:solicitud_detalle", args=[reserva.pk]),
        )

    def test_req_sol_008_anonimo_es_redirigido_al_login(self):
        ruta = reverse("reservations:solicitud_lista")

        respuesta = self.client.get(ruta)

        self.assert_redirige_al_login(respuesta, ruta)

    # REQ-SOL-009: visibilidad del detalle.

    def test_req_sol_009_solicitante_ve_detalle_con_datos(self):
        reserva = self.crear_reserva(motivo="Motivo visible completo")
        self.client.force_login(self.solicitante)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[reserva.pk])
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, reserva.espacio.nombre)
        self.assertContains(respuesta, reserva.fecha.strftime("%d/%m/%Y"))
        self.assertContains(respuesta, "10:00")
        self.assertContains(respuesta, "11:00")
        self.assertContains(respuesta, "Motivo visible completo")
        self.assertContains(respuesta, "Pendiente")

    def test_req_sol_009_otro_solicitante_recibe_403(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.otro_solicitante)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[reserva.pk])
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertNotContains(
            respuesta,
            reserva.motivo,
            status_code=403,
        )

    def test_req_sol_009_aprobador_ve_cualquier_detalle(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[reserva.pk])
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_req_sol_009_administrador_ve_cualquier_detalle(self):
        reserva = self.crear_reserva()
        self.client.force_login(self.administrador)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[reserva.pk])
        )

        self.assertEqual(respuesta.status_code, 200)

    def test_req_sol_009_anonimo_es_redirigido_al_login(self):
        reserva = self.crear_reserva()
        ruta = reverse("reservations:solicitud_detalle", args=[reserva.pk])

        respuesta = self.client.get(ruta)

        self.assert_redirige_al_login(respuesta, ruta)

    def test_req_sol_009_solicitud_inexistente_devuelve_404(self):
        self.client.force_login(self.aprobador)

        respuesta = self.client.get(
            reverse("reservations:solicitud_detalle", args=[999999])
        )

        self.assertEqual(respuesta.status_code, 404)


class DisponibilidadViewTests(TestCase):
    """Consulta de franjas ocupadas por espacio y fecha."""

    @classmethod
    def setUpTestData(cls):
        cls.espacio = crear_espacio(nombre="Auditorio Consulta")
        cls.inactivo = crear_espacio(
            nombre="Auditorio Inactivo Consulta",
            activo=False,
        )
        cls.usuario = crear_usuario(rol=Rol.SOLICITANTE)
        cls.aprobador = crear_usuario(rol=Rol.APROBADOR)
        cls.fecha = date.today() + timedelta(days=25)
        cls.fecha_libre = date.today() + timedelta(days=26)

    def parametros(self, **cambios):
        datos = {
            "espacio": self.espacio.pk,
            "fecha": self.fecha.isoformat(),
        }
        datos.update(cambios)
        return datos

    def crear_aprobada(self, **cambios):
        datos = {
            "espacio": self.espacio,
            "solicitante": self.usuario,
            "fecha": self.fecha,
            "hora_inicio": time(10, 0),
            "hora_fin": time(12, 0),
        }
        datos.update(cambios)
        return crear_reserva_aprobada(**datos)

    def crear_estado(self, estado, **cambios):
        datos = {
            "espacio": self.espacio,
            "solicitante": self.usuario,
            "fecha": self.fecha,
            "hora_inicio": time(14, 0),
            "hora_fin": time(16, 0),
            "estado": estado,
        }
        datos.update(cambios)
        return crear_reserva(**datos)

    def test_req_dis_008_lista_solo_franjas_aprobadas(self):
        self.crear_aprobada()
        self.crear_estado(EstadoReserva.PENDIENTE)
        self.crear_estado(
            EstadoReserva.CANCELADA,
            hora_inicio=time(8, 0),
            hora_fin=time(9, 0),
        )
        self.crear_estado(
            EstadoReserva.RECHAZADA,
            hora_inicio=time(16, 0),
            hora_fin=time(17, 0),
        )
        self.client.force_login(self.usuario)

        respuesta = self.client.get(
            reverse("reservations:disponibilidad"),
            self.parametros(),
        )

        self.assertEqual(respuesta.status_code, 200)
        franjas = list(respuesta.context["franjas"])
        self.assertEqual(len(franjas), 1)
        self.assertEqual(franjas[0].hora_inicio, time(10, 0))
        self.assertEqual(franjas[0].hora_fin, time(12, 0))
        self.assertContains(respuesta, "10:00")
        self.assertContains(respuesta, "12:00")
        self.assertNotContains(respuesta, "14:00")
        self.assertNotContains(respuesta, "08:00")

    def test_req_dis_008_franjas_ordenadas_por_hora_inicio(self):
        self.crear_aprobada(
            hora_inicio=time(14, 0),
            hora_fin=time(16, 0),
        )
        self.crear_aprobada(
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
        )
        self.client.force_login(self.usuario)

        respuesta = self.client.get(
            reverse("reservations:disponibilidad"),
            self.parametros(),
        )

        self.assertEqual(
            [franja.hora_inicio for franja in respuesta.context["franjas"]],
            [time(10, 0), time(14, 0)],
        )

    def test_req_dis_008_fecha_sin_aprobadas_muestra_mensaje_libre(self):
        self.crear_estado(
            EstadoReserva.PENDIENTE,
            fecha=self.fecha_libre,
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
        )
        self.client.force_login(self.usuario)

        respuesta = self.client.get(
            reverse("reservations:disponibilidad"),
            self.parametros(fecha=self.fecha_libre.isoformat()),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context["franjas"]), [])
        self.assertContains(respuesta, "No hay franjas ocupadas")

    def test_req_dis_008_parametros_invalidos_muestran_errores_sin_franjas(self):
        self.crear_aprobada()
        self.client.force_login(self.usuario)

        respuesta = self.client.get(
            reverse("reservations:disponibilidad"),
            self.parametros(fecha="no-es-fecha"),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("fecha", respuesta.context["form"].errors)
        self.assertEqual(list(respuesta.context["franjas"]), [])
        self.assertFalse(respuesta.context["consultado"])

    def test_req_dis_008_espacio_inactivo_es_invalido(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(
            reverse("reservations:disponibilidad"),
            self.parametros(espacio=self.inactivo.pk),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("espacio", respuesta.context["form"].errors)
        self.assertEqual(list(respuesta.context["franjas"]), [])

    def test_req_dis_008_anonimo_es_redirigido_al_login(self):
        ruta = reverse("reservations:disponibilidad")
        parametros = self.parametros()

        respuesta = self.client.get(ruta, parametros)

        self.assertEqual(respuesta.status_code, 302)
        destino = urlparse(respuesta["Location"])
        self.assertEqual(destino.path, reverse("accounts:login"))
        self.assertEqual(
            parse_qs(destino.query)["next"],
            [f"{ruta}?espacio={parametros['espacio']}"
             f"&fecha={parametros['fecha']}"],
        )

    def test_req_dis_008_consulta_se_recalcula_tras_aprobar(self):
        pendiente = self.crear_estado(
            EstadoReserva.PENDIENTE,
            hora_inicio=time(10, 0),
            hora_fin=time(12, 0),
        )
        self.client.force_login(self.usuario)
        ruta = reverse("reservations:disponibilidad")

        antes = self.client.get(ruta, self.parametros())
        self.assertContains(antes, "No hay franjas ocupadas")

        aprobar_reserva(reserva=pendiente, actor=self.aprobador)

        despues = self.client.get(ruta, self.parametros())
        self.assertContains(despues, "10:00")
        self.assertContains(despues, "12:00")
        self.assertNotContains(despues, "No hay franjas ocupadas")
