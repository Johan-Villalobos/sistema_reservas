"""Vistas de las solicitudes de reserva."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from .forms import DisponibilidadForm, SolicitudReservaForm
from .models import Reserva
from .permissions import puede_ver_solicitud
from .services import crear_solicitud, franjas_ocupadas


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
