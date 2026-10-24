# Tasks

Precondición: `base-proyecto`, `usuarios-roles-permisos` y `gestion-espacios`
implementados, con `accounts.Usuario`, roles, mecanismo de permisos y
`spaces.EspacioAcademico` operativos.

## 1. Modelo Reserva

- [x] 1.1 Crear `EstadoReserva(models.TextChoices)` en `reservations/models.py` con `PENDIENTE`, `APROBADA`, `RECHAZADA` y `CANCELADA`, usando los valores en mayúsculas como identificadores; verificar con `python manage.py shell -c "from reservations.models import EstadoReserva; print(list(EstadoReserva))"` que se listan los cuatro.
- [x] 1.2 Implementar `Reserva` con `espacio` (`ForeignKey` a `spaces.EspacioAcademico`, `on_delete=PROTECT`, `related_name="reservas"`), `solicitante` (`ForeignKey` a `settings.AUTH_USER_MODEL`, `on_delete=PROTECT`, `related_name="reservas_solicitadas"`), `fecha`, `hora_inicio`, `hora_fin`, `motivo` (máx. 255), `estado` con valor por defecto `PENDIENTE`, `creado_en` (`auto_now_add`) y `actualizado_en` (`auto_now`); verificar con `python manage.py makemigrations reservations --dry-run --verbosity 3` que la migración propuesta incluye todos los campos y las claves foráneas.
- [x] 1.3 Agregar a `Meta` `ordering = ["-fecha", "-hora_inicio"]` y la restricción `CheckConstraint(check=Q(hora_fin__gt=F("hora_inicio")), name="ck_reserva_hora_fin_mayor")`; verificar que el dry-run de migración incluye la restricción con ese nombre.
- [x] 1.4 Implementar `__str__` con espacio, fecha y franja; verificar en `python manage.py shell` que la representación incluye el nombre del espacio y la fecha.

## 2. Migración

- [x] 2.1 Generar `reservations/migrations/0001_initial.py` con `python manage.py makemigrations reservations`; verificar que contiene `CreateModel`, las dos claves foráneas con `PROTECT` y el `CheckConstraint` de horas.
- [x] 2.2 Aplicar `python manage.py migrate` y verificar código de salida 0, la tabla `reservations_reserva` con sus columnas y las claves foráneas mediante `python manage.py shell` e introspección de base de datos.
- [x] 2.3 Comprobar la restricción de base de datos: intentar insertar por ORM una reserva con `hora_fin` menor o igual a `hora_inicio` y verificar que lanza `IntegrityError` y no deja fila insertada.
- [x] 2.4 Verificar la reproducibilidad en base limpia: eliminar `db.sqlite3`, ejecutar `python manage.py migrate` y confirmar código 0, `showmigrations` sin pendientes y `python manage.py makemigrations --check --dry-run` sin cambios detectados.

## 3. Formulario

- [x] 3.1 Implementar `SolicitudReservaForm(ModelForm)` en `reservations/forms.py` con `espacio`, `fecha`, `hora_inicio`, `hora_fin` y `motivo`, excluyendo `solicitante`, `estado` y campos de auditoría; verificar en `python manage.py shell` que `form.fields` contiene exactamente esos cinco campos.
- [x] 3.2 Limitar el queryset de `espacio` a `EspacioAcademico.objects.activos()` ordenado por nombre y configurar widgets HTML5 `type="date"` y `type="time"` con clases de Bootstrap; verificar en `python manage.py shell` que un espacio inactivo no es una opción válida del campo y que un activo sí lo es.
- [x] 3.3 Configurar `motivo` como obligatorio con máximo 255 caracteres y etiquetas de ayuda del horario operativo en el formulario; verificar en `python manage.py shell` que un motivo vacío, uno de 255 caracteres y uno de 256 producen resultados de validez distintos.

## 4. Servicio de creación y permisos

- [x] 4.1 Agregar a `config/settings.py` `HORARIO_OPERATIVO_INICIO = "06:00"` y `HORARIO_OPERATIVO_FIN = "22:00"`; verificar con `python manage.py shell -c "from django.conf import settings; print(settings.HORARIO_OPERATIVO_INICIO, settings.HORARIO_OPERATIVO_FIN)"`.
- [x] 4.2 Implementar en `reservations/services.py` `obtener_horario_operativo()` que parsee ambos settings con `time.fromisoformat` y lance `ImproperlyConfigured` si son inválidos o si inicio ≥ fin; verificar con `override_settings` en `python manage.py shell` que un valor inválido lanza la excepción y que el valor por defecto devuelve 06:00 y 22:00.
- [x] 4.3 Implementar `validar_solicitud(*, espacio, fecha, hora_inicio, hora_fin, motivo, ahora=None)` con las reglas de hora de fin mayor, mismo día, motivo obligatorio y máximo 255, espacio activo, inicio no pasado y franja dentro del horario con extremos inclusivos, lanzando `ValidationError` con claves de campo; verificar en `python manage.py shell` con casos de hora igual, hora invertida, espacio inactivo, motivo vacío, fecha de ayer y horas 05:59/06:00/22:00/22:01.
- [x] 4.4 Implementar `crear_solicitud(*, espacio, solicitante, fecha, hora_inicio, hora_fin, motivo)` con `@transaction.atomic`, revalidando dentro de la transacción, reconsultando que el espacio siga activo y creando siempre con `estado=PENDIENTE`; verificar en `python manage.py shell` que no acepta un parámetro de estado, que la reserva creada queda `PENDIENTE` con el solicitante recibido y que la vista no asigna `estado` directamente (REQ-SOL-011).
- [x] 4.5 Implementar `reservations/permissions.py` con `puede_ver_solicitud(usuario, reserva)`, verdadero para el solicitante o para roles `APROBADOR`/`ADMINISTRADOR` autenticados; verificar con `python manage.py shell` los cuatro casos (dueño, aprobador, administrador y otro solicitante).
- [x] 4.6 Conectar `SolicitudReservaForm.clean()` con `validar_solicitud` para que los errores del servicio se asocien a los campos correspondientes; verificar en `python manage.py shell` que un formulario con hora invertida presenta el error en `hora_fin` y uno con espacio inactivo en `espacio`.

## 5. Vistas y rutas

- [x] 5.1 Implementar `SolicitudCreateView(LoginRequiredMixin, CreateView)` con `SolicitudReservaForm`: en `form_valid` invocar `crear_solicitud` con `solicitante=request.user`, capturar `ValidationError` y devolver el formulario con errores, y en éxito redirigir al detalle con mensaje; verificar con el cliente de pruebas que un usuario activo crea con cualquiera de los tres roles (`SOLICITANTE`, `APROBADOR`, `ADMINISTRADOR`) y que un POST con `estado=APROBADA` sigue produciendo `PENDIENTE`.
- [x] 5.2 Implementar `SolicitudListView(LoginRequiredMixin, ListView)` con queryset filtrado por `solicitante=request.user` y `select_related("espacio")`; verificar con el cliente de pruebas que el listado de un usuario no contiene reservas de otro usuario.
- [x] 5.3 Implementar `SolicitudDetailView(LoginRequiredMixin, DetailView)` con comprobación en `dispatch` mediante `puede_ver_solicitud`; verificar que el dueño, un aprobador y un administrador obtienen 200, que otro solicitante obtiene 403 y que un identificador inexistente devuelve 404.
- [x] 5.4 Crear `reservations/urls.py` con los nombres `reservations:solicitud_lista`, `reservations:solicitud_crear` y `reservations:solicitud_detalle`, e incluirlo en `config/urls.py` bajo `reservas/`; verificar con `python manage.py check` y con `reverse` de los tres nombres.

## 6. Plantillas

- [x] 6.1 Crear `reservations/templates/reservations/solicitud_lista.html` con tabla de espacio, fecha, hora de inicio, hora de fin, estado y enlace al detalle, botón "Nueva solicitud" y estado vacío; verificar que un usuario sin solicitudes ve el estado vacío y que sus filas muestran el estado `PENDIENTE`.
- [x] 6.2 Crear `reservations/templates/reservations/solicitud_form.html` con los cinco campos, errores por campo, ayuda del horario operativo y botones de enviar y cancelar; verificar que los errores de hora y motivo aparecen junto a su campo y que no existe campo de fecha de fin.
- [x] 6.3 Crear `reservations/templates/reservations/solicitud_detalle.html` con espacio, solicitante, fecha, franja, motivo, estado y fecha de creación, más el botón de volver al listado; verificar que muestra el motivo completo y no ofrece acciones de aprobación ni cancelación.
- [x] 6.4 Actualizar `templates/base.html` para enlazar "Reservas" con `{% url 'reservations:solicitud_lista' %}` visible para usuarios autenticados; verificar que un anónimo no ve el enlace y que un usuario autenticado navega al listado sin errores.

## 7. Pruebas de la capacidad

- [x] 7.1 Crear `reservations/tests/__init__.py` y `reservations/tests/utils.py` con helpers para crear usuarios por rol, espacios activos/inactivos y datos de solicitud con fecha de mañana; verificar con `python manage.py test reservations` que el paquete se descubre sin errores.
- [x] 7.2 Escribir `reservations/tests/test_models.py`: valor por defecto `PENDIENTE`, `creado_en` asignado, `__str__`, relaciones con espacio y solicitante y `IntegrityError` al insertar horas inválidas por ORM; verificar con `python manage.py test reservations.tests.test_models` (cubre REQ-SOL-002 y REQ-SOL-010).
- [x] 7.3 Escribir `reservations/tests/test_forms.py`: campos expuestos, selector solo con espacios activos, motivo vacío/255/256, hora igual y hora invertida con error en el campo correcto; verificar con `python manage.py test reservations.tests.test_forms` (cubre REQ-SOL-003, REQ-SOL-005 y REQ-SOL-006).
- [x] 7.4 Escribir `reservations/tests/test_services.py`: creación válida con estado `PENDIENTE` y solicitante de sesión, creación por cada rol (`SOLICITANTE`, `APROBADOR`, `ADMINISTRADOR`), estado enviado ignorado, hora igual, hora invertida, fecha de ayer, hora transcurrida hoy con `ahora` inyectado, espacio inactivo, límites 05:59/06:00/22:00/22:01, motivo límite, `override_settings` de horario 08:00–18:00 y verificación de que `estado` solo se escribe mediante `crear_solicitud` (REQ-SOL-011); verificar con `python manage.py test reservations.tests.test_services` (cubre REQ-SOL-001 a REQ-SOL-007 y REQ-SOL-011).
- [x] 7.5 Escribir `reservations/tests/test_views.py`: creación autenticada por cada rol, anónimo redirigido con `next` en crear/listar/detalle, listado solo con solicitudes propias, detalle 200 para dueño/aprobador/administrador, 403 para otro solicitante, 404 para inexistente y verificación de que la respuesta de detalle muestra espacio, fecha, franja, motivo y estado; verificar con `python manage.py test reservations.tests.test_views` (cubre REQ-SOL-001, REQ-SOL-008 y REQ-SOL-009).
- [x] 7.6 Documentar en `reservations/tests/test_models.py` o `test_services.py` la limitación de SQLite: una escritura directa de `estado` por ORM no se impide en base de datos y no se considera una transición soportada; verificar con `python manage.py test reservations` que la prueba deja constancia de la limitación sin presentarla como garantía.
- [x] 7.7 Ejecutar `python manage.py test` completo, `python manage.py check` y `python manage.py makemigrations --check --dry-run`; verificar que la suite pasa, no hay migraciones pendientes y cada escenario de `specs/solicitud-reserva/spec.md` tiene al menos una prueba cuyo nombre incluye el identificador del requisito.

## Workflow follow-up

- Revisar los artefactos, en particular la decisión de horario operativo 06:00–22:00 con extremos inclusivos.
- Implementar después de `base-proyecto`, `usuarios-roles-permisos` y `gestion-espacios`.
- Tras las pruebas en verde, archivar el cambio para crear la especificación vigente de `solicitud-reserva`.
- Registrar para `disponibilidad` que debe extender `crear_solicitud` con la detección de solapamientos y decidir el efecto de las solicitudes `PENDIENTE`.
- Registrar para `aprobación` que debe agregar `revisado_por`, `motivo_decision`, `fecha_decision`, `HistorialReserva` y las transiciones de estado, siempre dentro de `reservations/services.py`.
