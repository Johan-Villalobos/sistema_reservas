"""Vistas de las solicitudes de reserva."""

from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    FormView,
    ListView,
    TemplateView,
)

from accounts.permissions import RolRequeridoMixin, usuario_tiene_rol
from accounts.roles import Rol
from spaces.models import EspacioAcademico

from .forms import DisponibilidadForm, RechazarReservaForm, SolicitudReservaForm
from .models import EstadoReserva, HistorialReserva, Reserva
from .permissions import (
    es_administrador,
    puede_cancelar_reserva,
    puede_decidir_reserva,
    puede_ver_historial,
    puede_ver_solicitud,
)
from .services import (
    aprobar_reserva,
    cancelar_reserva,
    crear_solicitud,
    franjas_ocupadas,
    motivo_no_cancelable,
    rechazar_reserva,
)


def _mensajes_de_error(error):
    """Aplana un ``ValidationError`` en una lista de mensajes legibles."""
    if hasattr(error, "message_dict"):
        return [
            mensaje
            for mensajes in error.message_dict.values()
            for mensaje in mensajes
        ]
    return list(error.messages)


class SolicitudCreateView(LoginRequiredMixin, CreateView):
    """Creación de una solicitud a nombre del usuario autenticado."""

    model = Reserva
    form_class = SolicitudReservaForm
    template_name = "reservations/solicitud_form.html"

    def form_valid(self, form):
        try:
            self.object = crear_solicitud(
                **form.cleaned_data,
                solicitante=self.request.user,
            )
        except DjangoValidationError as error:
            for campo, mensajes in getattr(error, "message_dict", {}).items():
                for mensaje in mensajes:
                    form.add_error(campo, mensaje)
            if not hasattr(error, "message_dict"):
                form.add_error(None, error)
            return self.form_invalid(form)

        messages.success(
            self.request,
            "La solicitud de reserva se creó correctamente.",
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse(
            "reservations:solicitud_detalle",
            kwargs={"pk": self.object.pk},
        )


class SolicitudListView(LoginRequiredMixin, ListView):
    """Listado de las solicitudes del usuario autenticado."""

    model = Reserva
    template_name = "reservations/solicitud_lista.html"
    context_object_name = "solicitudes"

    def get_queryset(self):
        return Reserva.objects.filter(
            solicitante=self.request.user
        ).select_related("espacio")


class SolicitudDetailView(LoginRequiredMixin, DetailView):
    """Detalle visible para el solicitante, aprobadores y administradores."""

    model = Reserva
    template_name = "reservations/solicitud_detalle.html"
    context_object_name = "solicitud"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.object = self.get_object()
            if not puede_ver_solicitud(request.user, self.object):
                raise PermissionDenied(
                    "No puede consultar esta solicitud de reserva."
                )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user

        ver_historial = puede_ver_historial(usuario, self.object)
        contexto["puede_ver_historial"] = ver_historial
        contexto["historial"] = (
            self.object.historial.select_related("actor").order_by(
                "fecha_evento",
                "pk",
            )
            if ver_historial
            else []
        )

        puede_cancelar = puede_cancelar_reserva(usuario, self.object)
        contexto["puede_ver_cancelacion"] = puede_cancelar
        contexto["motivo_no_cancelable"] = (
            motivo_no_cancelable(reserva=self.object)
            if puede_cancelar
            else None
        )
        return contexto


class HistorialReservaListView(LoginRequiredMixin, ListView):
    """Historial de reservas con alcance por usuario y filtros GET."""

    model = HistorialReserva
    template_name = "reservations/historial_lista.html"
    context_object_name = "historial"

    def get_queryset(self):
        queryset = HistorialReserva.objects.select_related(
            "reserva",
            "reserva__espacio",
            "reserva__solicitante",
            "actor",
        )
        if not es_administrador(self.request.user):
            queryset = queryset.filter(
                reserva__solicitante=self.request.user
            )
        queryset = queryset.order_by("-fecha_evento", "-pk")
        return queryset.filter(**self._filtros())

    def _filtros(self):
        filtros = {}

        estado = self.request.GET.get("estado")
        if estado in EstadoReserva.values:
            filtros["estado_nuevo"] = estado

        fecha_texto = self.request.GET.get("fecha")
        if fecha_texto:
            try:
                fecha = date.fromisoformat(fecha_texto)
            except (TypeError, ValueError):
                fecha = None
            if fecha is not None:
                filtros["fecha_evento__date"] = fecha

        espacio_texto = self.request.GET.get("espacio")
        if espacio_texto:
            try:
                espacio_id = int(espacio_texto)
            except (TypeError, ValueError):
                espacio_id = None
            if (
                espacio_id is not None
                and EspacioAcademico.objects.filter(pk=espacio_id).exists()
            ):
                filtros["reserva__espacio_id"] = espacio_id

        return filtros

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        filtros = self._filtros()
        fecha = filtros.get("fecha_evento__date")
        contexto["filtros"] = {
            "estado": filtros.get("estado_nuevo", ""),
            "fecha": fecha.isoformat() if fecha else "",
            "espacio": filtros.get("reserva__espacio_id", ""),
        }
        contexto["estados"] = EstadoReserva.choices
        contexto["espacios"] = EspacioAcademico.objects.order_by("nombre")
        return contexto


class DisponibilidadView(LoginRequiredMixin, TemplateView):
    """Consulta de franjas ocupadas por reservas aprobadas."""

    template_name = "reservations/disponibilidad.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        formulario = DisponibilidadForm(self.request.GET or None)
        contexto["form"] = formulario
        contexto["consultado"] = False
        contexto["franjas"] = []

        if formulario.is_bound and formulario.is_valid():
            contexto["franjas"] = franjas_ocupadas(
                espacio=formulario.cleaned_data["espacio"],
                fecha=formulario.cleaned_data["fecha"],
            )
            contexto["consultado"] = True
        return contexto


class ReservaPendienteListView(RolRequeridoMixin, ListView):
    """Cola de solicitudes pendientes para aprobadores y administradores."""

    model = Reserva
    template_name = "reservations/solicitud_pendientes.html"
    context_object_name = "solicitudes"
    roles_permitidos = [Rol.APROBADOR, Rol.ADMINISTRADOR]

    def get_queryset(self):
        return (
            Reserva.objects.filter(estado=EstadoReserva.PENDIENTE)
            .select_related("espacio", "solicitante")
            .order_by("fecha", "hora_inicio", "creado_en", "pk")
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        for solicitud in contexto["solicitudes"]:
            solicitud.puede_decidir = puede_decidir_reserva(
                self.request.user,
                solicitud,
            )
        return contexto


class AprobarReservaView(RolRequeridoMixin, View):
    """Aprueba una solicitud pendiente mediante una acción POST."""

    http_method_names = ["post"]
    roles_permitidos = [Rol.APROBADOR, Rol.ADMINISTRADOR]

    def post(self, request, *args, **kwargs):
        reserva = get_object_or_404(Reserva, pk=kwargs["pk"])
        if not puede_decidir_reserva(request.user, reserva):
            raise PermissionDenied(
                "No puede decidir sobre su propia solicitud."
            )
        try:
            aprobar_reserva(reserva=reserva, actor=request.user)
        except DjangoValidationError as error:
            for mensaje in _mensajes_de_error(error):
                messages.error(request, mensaje)
            return render(
                request,
                "reservations/solicitud_detalle.html",
                {"solicitud": reserva},
            )

        messages.success(request, "La solicitud se aprobó correctamente.")
        return HttpResponseRedirect(reverse("reservations:pendientes"))


class RechazarReservaView(RolRequeridoMixin, FormView):
    """Rechaza una solicitud pendiente con un motivo obligatorio."""

    form_class = RechazarReservaForm
    template_name = "reservations/solicitud_rechazar.html"
    roles_permitidos = [Rol.APROBADOR, Rol.ADMINISTRADOR]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not usuario_tiene_rol(request.user, self.roles_permitidos):
            raise PermissionDenied(self.get_permission_denied_message())

        self.reserva = get_object_or_404(Reserva, pk=kwargs["pk"])
        if not puede_decidir_reserva(request.user, self.reserva):
            raise PermissionDenied(
                "No puede decidir sobre su propia solicitud."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["solicitud"] = self.reserva
        return contexto

    def form_valid(self, form):
        try:
            rechazar_reserva(
                reserva=self.reserva,
                actor=self.request.user,
                motivo=form.cleaned_data["motivo"],
            )
        except DjangoValidationError as error:
            for campo, mensajes in error.message_dict.items():
                destino = campo if campo in self.form_class.base_fields else None
                for mensaje in mensajes:
                    form.add_error(destino, mensaje)
            return self.form_invalid(form)

        messages.success(
            request=self.request,
            message="La solicitud se rechazó correctamente.",
        )
        return HttpResponseRedirect(reverse("reservations:pendientes"))


class CancelarReservaView(LoginRequiredMixin, View):
    """Confirma y ejecuta la cancelación de una reserva autorizada."""

    template_name = "reservations/solicitud_cancelar.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.reserva = get_object_or_404(
                Reserva.objects.select_related("espacio", "solicitante"),
                pk=kwargs["pk"],
            )
            if not puede_cancelar_reserva(request.user, self.reserva):
                raise PermissionDenied(
                    "No puede cancelar esta reserva."
                )
        return super().dispatch(request, *args, **kwargs)

    def _contexto(self, *, motivo, errores=None):
        return {
            "reserva": self.reserva,
            "motivo": motivo,
            "puede_confirmar": motivo is None,
            "errores": errores or [],
        }

    def get(self, request, *args, **kwargs):
        motivo = motivo_no_cancelable(reserva=self.reserva)
        return render(
            request,
            self.template_name,
            self._contexto(motivo=motivo),
        )

    def post(self, request, *args, **kwargs):
        try:
            cancelar_reserva(reserva=self.reserva, actor=request.user)
        except DjangoValidationError as error:
            self.reserva.refresh_from_db()
            motivo = motivo_no_cancelable(reserva=self.reserva)
            return render(
                request,
                self.template_name,
                self._contexto(
                    motivo=motivo,
                    errores=_mensajes_de_error(error),
                ),
            )

        messages.success(
            request,
            "La reserva se canceló correctamente.",
        )
        return HttpResponseRedirect(
            reverse(
                "reservations:solicitud_detalle",
                kwargs={"pk": self.reserva.pk},
            )
        )
