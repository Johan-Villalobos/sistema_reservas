"""Modelo de usuario del sistema."""

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower

from .roles import Rol


class UsuarioManager(UserManager):
    """Gestor que normaliza el correo a minúsculas antes de guardarlo."""

    def _normalizar_correo(self, email):
        if not email:
            return email
        return self.normalize_email(email.strip()).lower()

    def create_user(self, username, email=None, password=None, **extra_fields):
        return super().create_user(
            username,
            email=self._normalizar_correo(email),
            password=password,
            **extra_fields,
        )

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        return super().create_superuser(
            username,
            email=self._normalizar_correo(email),
            password=password,
            **extra_fields,
        )


class Usuario(AbstractUser):
    """Usuario del sistema con nombre completo, correo único y rol.

    ``base-proyecto`` fijó este modelo con ``AUTH_USER_MODEL`` y la migración
    inicial. Los campos de dominio se agregan aquí con una migración nueva.
    """

    email = models.EmailField("correo electrónico")
    nombre_completo = models.CharField(
        "nombre completo",
        max_length=150,
    )
    rol = models.CharField(
        "rol",
        max_length=13,
        choices=Rol.choices,
        default=Rol.SOLICITANTE,
    )

    REQUIRED_FIELDS = ["email", "nombre_completo"]

    objects = UsuarioManager()

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="uniq_usuario_email_ci",
            ),
        ]

    def get_full_name(self):
        """Devuelve el nombre completo de la persona."""
        return self.nombre_completo

    @property
    def es_administrador(self):
        """Indica si el usuario tiene el rol ADMINISTRADOR."""
        return self.rol == Rol.ADMINISTRADOR
