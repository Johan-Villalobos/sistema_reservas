"""Formulario de solicitud de reserva."""

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from spaces.models import EspacioAcademico

from .models import Reserva
from .services import validar_disponibilidad, validar_solicitud

CAMPOS_REQUERIDOS_PARA_VALIDAR = (
    "espacio",
    "fecha",
    "hora_inicio",
    "hora_fin",
    "motivo",
)


class SolicitudReservaForm(forms.ModelForm):
    """Datos de la solicitud; el solicitante y el estado vienen del servidor."""

    class Meta:
        model = Reserva
        fields = ("espacio", "fecha", "hora_inicio", "hora_fin", "motivo")
        labels = {
            "espacio": "Espacio",
            "fecha": "Fecha",
            "hora_inicio": "Hora de inicio",
            "hora_fin": "Hora de fin",
            "motivo": "Motivo",
        }
        widgets = {
            "espacio": forms.Select(attrs={"class": "form-select"}),
            "fecha": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "hora_inicio": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "hora_fin": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "motivo": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["espacio"].queryset = (
            EspacioAcademico.objects.activos().order_by("nombre")
        )

        horario = (
            f"Horario operativo: {settings.HORARIO_OPERATIVO_INICIO} "
            f"a {settings.HORARIO_OPERATIVO_FIN}."
        )
        self.fields["hora_inicio"].help_text = horario
        self.fields["hora_fin"].help_text = (
            f"Debe ser posterior a la hora de inicio. {horario}"
        )

    def clean(self):
        datos = super().clean()
        if not all(
            campo in datos for campo in CAMPOS_REQUERIDOS_PARA_VALIDAR
        ):
            return datos

        try:
            validar_solicitud(
                espacio=datos["espacio"],
                fecha=datos["fecha"],
                hora_inicio=datos["hora_inicio"],
                hora_fin=datos["hora_fin"],
                motivo=datos["motivo"],
            )
            validar_disponibilidad(
                espacio=datos["espacio"],
                fecha=datos["fecha"],
                hora_inicio=datos["hora_inicio"],
                hora_fin=datos["hora_fin"],
            )
        except ValidationError as error:
            for campo, mensajes in error.message_dict.items():
                for mensaje in mensajes:
                    self.add_error(campo, mensaje)
        return datos


class DisponibilidadForm(forms.Form):
    """Consulta de franjas ocupadas por espacio y fecha."""

    espacio = forms.ModelChoiceField(
        queryset=EspacioAcademico.objects.activos().order_by("nombre"),
        label="Espacio",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha = forms.DateField(
        label="Fecha",
        initial=timezone.localdate,
        widget=forms.DateInput(
            attrs={"class": "form-control", "type": "date"}
        ),
    )


class RechazarReservaForm(forms.Form):
    """Motivo obligatorio para rechazar una solicitud pendiente."""

    motivo = forms.CharField(
        label="Motivo del rechazo",
        strip=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Explique por qué se rechaza la solicitud",
            }
        ),
        error_messages={
            "required": "El motivo del rechazo es obligatorio.",
        },
    )

    def clean_motivo(self):
        motivo = (self.cleaned_data.get("motivo") or "").strip()
        if not motivo:
            raise ValidationError("El motivo del rechazo es obligatorio.")
        return motivo
