# Tasks

Precondición: `solicitud-reserva` y `disponibilidad-simultaneidad` implementados, con
`Reserva`, `EstadoReserva`, `validar_disponibilidad`, `crear_solicitud` y sus suites en
verde.

## 1. Modelo y migración

- [x] 1.1 Agregar `revisado_por` (`ForeignKey` nullable a `settings.AUTH_USER_MODEL`, `on_delete=SET_NULL`, `related_name="reservas_revisadas"`), `motivo_decision` (`TextField(blank=True, default="")`) y `fecha_decision` (`DateTimeField(null=True, blank=True)`) a `Reserva`; verificar en `python manage.py shell` que los tres campos existen con la nulabilidad y el valor por defecto esperados.
- [x] 1.2 Generar `reservations/migrations/0002_...` con `AddField` para los tres campos, aplicar `python manage.py migrate` y verificar en `python manage.py shell` que una reserva existente conserva `revisado_por=None`, `motivo_decision=""` y `fecha_decision=None`.
- [x] 1.3 Ampliar `reservations/tests/test_models.py` con los valores iniciales de los campos, su comportamiento al guardar una decisión y que `fecha_decision` es independiente de `actualizado_en`; verificar con `python manage.py test reservations.tests.test_models`.

## 2. Servicios y máquina de estados

- [x] 2.1 Implementar en `reservations/services.py` el mapa `TRANSICIONES_APROBACION` con `PENDIENTE → APROBADA` y `PENDIENTE → RECHAZADA`, y la función interna `_decidir_reserva(*, reserva, actor, nuevo_estado, motivo_decision="")` con `transaction.atomic`, recarga con `select_for_update`, comprobación de rol, prohibición de autodecisión, validación de la transición, actualización condicional por `estado=PENDIENTE` y recarga final; verificar en `python manage.py shell` una aprobación válida, un rechazo válido, una transición desde `APROBADA` que lanza `ValidationError`, un actor `SOLICITANTE` y un actor que es el solicitante, ambos con `PermissionDenied`.
- [x] 2.2 Implementar `aprobar_reserva(*, reserva, actor)` sobre `_decidir_reserva`: bloquear el espacio, llamar a `validar_disponibilidad(..., excluir_reserva=reserva.pk)`, fijar `estado=APROBADA`, `revisado_por=actor`, `motivo_decision=""`, `fecha_decision=timezone.now()` y `actualizado_en`; verificar en `python manage.py shell` que una solicitud sin conflicto queda `APROBADA` y que una solicitud que se cruza con una aprobada lanza `ValidationError` y permanece `PENDIENTE`.
- [x] 2.3 Implementar `rechazar_reserva(*, reserva, actor, motivo)` sobre `_decidir_reserva`: normalizar el motivo con `strip()`, rechazar vacío o compuesto solo por espacios con `ValidationError` en `motivo`, y fijar `estado=RECHAZADA`, `revisado_por=actor`, `motivo_decision` normalizado, `fecha_decision=timezone.now()` y `actualizado_en`; verificar en `python manage.py shell` un rechazo con motivo, uno con motivo vacío, uno con solo espacios y uno de una solicitud que se cruza con una aprobada.
- [x] 2.4 Agregar a `reservations/tests/test_aprobacion.py` las pruebas de servicio: aprobación válida, administrador, revisor y `fecha_decision`, motivo vacío en aprobación, rechazo con motivo, motivo vacío, solo espacios, normalización, estados no pendientes, autodecisión, actor sin rol o anónimo, conflicto de disponibilidad, conflicto creado después de la solicitud, dos pendientes que se cruzan, rechazo en conflicto y actualización condicional; verificar con `python manage.py test reservations.tests.test_aprobacion`.
- [x] 2.5 Documentar en los docstrings de `aprobar_reserva`, `rechazar_reserva` y `_decidir_reserva` la transacción, la revalidación, el bloqueo del espacio, la actualización condicional, el registro de `fecha_decision` y la limitación de `select_for_update` en SQLite; verificar que el texto coincide con el comportamiento cubierto por las pruebas del grupo 2.

## 3. Vistas y rutas

- [x] 3.1 Implementar `ReservaPendienteListView` en `reservations/views.py` con `Reserva.objects.filter(estado=EstadoReserva.PENDIENTE).select_related("espacio", "solicitante").order_by("fecha", "hora_inicio", "creado_en", "pk")` y contexto con las reservas y el indicador de decisión; verificar con el cliente de pruebas que solo lista pendientes, respeta el orden y muestra el estado vacío.
- [x] 3.2 Implementar `AprobarReservaView(View)` con `http_method_names = ["post"]`, `get_object_or_404`, llamada a `aprobar_reserva` y redirección a `reservations:pendientes` con mensaje de éxito; en `ValidationError`, renderizar `solicitud_detalle.html` con la reserva y el mensaje; verificar con el cliente de pruebas el éxito, el 405 en GET, el 404, el conflicto con mensaje y el estado sin cambios.
- [x] 3.3 Implementar `RechazarReservaForm(forms.Form)` en `reservations/forms.py` con `motivo` obligatorio, `strip=True`, `Textarea` y `clean_motivo` que rechaza vacío o solo espacios; verificar con `python manage.py test reservations.tests.test_forms` los casos vacío, solo espacios y motivo válido.
- [x] 3.4 Implementar `RechazarReservaView(FormView)` con `RechazarReservaForm`, `solicitud_rechazar.html`, carga de la reserva en `dispatch()` y llamada a `rechazar_reserva` en `form_valid()`; en éxito redirigir a `reservations:pendientes` y en `ValidationError` de estado agregar el error al formulario; verificar con el cliente de pruebas el GET, el POST válido, el motivo inválido, el estado no pendiente y el 404.
- [x] 3.5 Agregar las rutas `reservas/pendientes/`, `reservas/<int:pk>/aprobar/` y `reservas/<int:pk>/rechazar/` con los nombres `reservations:pendientes`, `reservations:aprobar` y `reservations:rechazar`; verificar con `python manage.py check` y con `reverse()` que cada nombre resuelve a la ruta esperada.
- [x] 3.6 Ampliar `reservations/tests/test_aprobacion.py` con las pruebas de las tres vistas (contenido, redirecciones, 405, 404 y errores de estado); verificar con `python manage.py test reservations.tests.test_aprobacion`.

## 4. Plantillas y navegación

- [x] 4.1 Crear `reservations/templates/reservations/solicitud_pendientes.html` con tabla de espacio, solicitante, fecha, franja y motivo; formulario POST con `{% csrf_token %}` para aprobar y enlace al rechazo por fila; indicación para la solicitud propia sin acciones y estado vacío; verificar con el cliente de pruebas que una fila decidible muestra ambas acciones y que la propia no las muestra.
- [x] 4.2 Crear `reservations/templates/reservations/solicitud_rechazar.html` con el resumen de la solicitud, el formulario de motivo, los errores por campo y no de campo, y los botones de confirmar y cancelar; verificar que el GET muestra el campo y que un POST sin motivo vuelve a mostrar el error junto al campo.
- [x] 4.3 Ampliar `solicitud_detalle.html` con una sección de decisión que muestre el estado, el revisor y, cuando exista, el motivo con `linebreaksbr`, sin mostrar revisor ni motivo en estado `PENDIENTE`; verificar con el cliente de pruebas los casos aprobado, rechazado y pendiente.
- [x] 4.4 Agregar el enlace "Pendientes" a `templates/base.html` solo para usuarios autenticados con rol `APROBADOR` o `ADMINISTRADOR`; verificar que un `SOLICITANTE` y un anónimo no ven el enlace y que ambos roles privilegiados sí lo ven.
- [x] 4.5 Verificar que las plantillas nuevas extienden `base.html`, usan las clases Bootstrap del proyecto y no requieren JavaScript; comprobar con el cliente de pruebas que las páginas se renderizan sin errores de plantilla.

## 5. Permisos

- [x] 5.1 Implementar `puede_decidir_reserva(usuario, reserva)` en `reservations/permissions.py`: verdadero solo si el usuario está autenticado, tiene rol `APROBADOR` o `ADMINISTRADOR` y no es el solicitante; verificar con pruebas unitarias los casos de cada rol, el solicitante y el usuario anónimo.
- [x] 5.2 Aplicar `puede_decidir_reserva` en `AprobarReservaView`, `RechazarReservaView` y en el contexto de la cola; verificar con el cliente de pruebas que la autodecisión devuelve 403, que la solicitud permanece `PENDIENTE` y que la fila propia no ofrece acciones.
- [x] 5.3 Aplicar `RolRequeridoMixin` con `roles_permitidos = [Rol.APROBADOR, Rol.ADMINISTRADOR]` a las tres vistas; verificar con el cliente de pruebas que un `SOLICITANTE` recibe 403 en cola, aprobación y rechazo, y que un anónimo es redirigido al login con `next` en las tres rutas.
- [x] 5.4 Agregar a `reservations/tests/test_aprobacion.py` las pruebas de permisos de `REQ-APR-005` y `REQ-APR-006`: autodecisión de aprobador y administrador, `SOLICITANTE` en cada acción y anónimo en cada ruta; verificar con `python manage.py test reservations.tests.test_aprobacion`.
- [x] 5.5 Comprobar que los 403 usan la plantilla `403.html` existente y que los mensajes no exponen datos internos; verificar con el cliente de pruebas el estado y el contenido de la respuesta.

## 6. Pruebas de integración y verificación final

- [x] 6.1 Escribir una prueba de integración del flujo de aprobación: crear una solicitud, verla en la cola como aprobador, aprobarla desde la ruta POST y comprobar en el detalle el estado `APROBADA` y el revisor; verificar con `python manage.py test reservations.tests.test_aprobacion`.
- [x] 6.2 Escribir una prueba de integración del flujo de rechazo: crear una solicitud, rechazarla con motivo desde el formulario y comprobar que el solicitante ve el estado `RECHAZADA`, el motivo completo y el revisor; verificar con `python manage.py test reservations.tests.test_aprobacion`.
- [x] 6.3 Escribir una prueba de integración de conflicto: crear dos solicitudes pendientes que se cruzan, aprobar la primera y comprobar que la segunda no puede aprobarse, muestra el mensaje con espacio, fecha y franja, y permanece `PENDIENTE`; repetir con una reserva aprobada creada después de la solicitud; verificar con `python manage.py test reservations.tests.test_aprobacion`.
- [x] 6.4 Ejecutar `python manage.py test`, `python manage.py check` y `python manage.py makemigrations --check --dry-run`; verificar que la suite completa pasa, que no hay errores de configuración y que no quedan migraciones pendientes ni nuevas.
- [x] 6.5 Verificar la trazabilidad: cada escenario de `specs/aprobacion-rechazo/spec.md` tiene al menos una prueba cuyo nombre o docstring incluye `REQ-APR-00X`; documentar la matriz requisito-escenario-prueba en el informe de cierre.
- [x] 6.6 Ejecutar la verificación manual guiada: recorrer con un aprobador, un administrador, un solicitante y un anónimo la cola, la aprobación, el rechazo, el detalle y los 403/redirecciones; registrar el resultado en la lista de verificación del cierre.

## Workflow follow-up

- Revisar y confirmar en la revisión de especificaciones la prohibición de autodecisión, la ausencia de límite para el motivo de rechazo y el uso de `fecha_decision` como fecha de decisión, distinta de `actualizado_en`.
- Implementar este cambio después de `solicitud-reserva` y `disponibilidad-simultaneidad`, con sus suites en verde.
- Archivar el cambio cuando la suite completa y la verificación manual estén conformes, para crear la especificación vigente de `aprobacion-rechazo`.
- Registrar para el cambio de cancelación e historial: extender la máquina de estados con `PENDIENTE → CANCELADA` y `APROBADA → CANCELADA`, agregar `HistorialReserva` y conservar `fecha_decision` sin sobrescribirla al cancelar.
- Registrar para el cierre que la mitigación de concurrencia depende de la transacción, la revalidación, el bloqueo del espacio y la actualización condicional; documentar la limitación de SQLite en el informe final.
