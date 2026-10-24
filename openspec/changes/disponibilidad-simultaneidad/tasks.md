# Tasks

Precondición: `solicitud-reserva` implementado, con modelo `Reserva`, estados,
`crear_solicitud` y el formulario de solicitud operativos.

## 1. Servicio de validación de cruces

- [ ] 1.1 Implementar `validar_disponibilidad(*, espacio, fecha, hora_inicio, hora_fin, excluir_reserva=None)` en `reservations/services.py`, consultando reservas `APROBADA` del mismo espacio y fecha con `hora_inicio__lt=hora_fin` y `hora_fin__gt=hora_inicio`, excluyendo la reserva indicada; verificar en `python manage.py shell` con una reserva aprobada de 10:00 a 12:00 que las franjas 10:00–12:00, 09:00–11:00, 11:00–13:00, 10:30–11:30 y 09:00–13:00 lanzan `ValidationError`.
- [ ] 1.2 Construir el mensaje de conflicto con nombre del espacio, fecha y franja de la reserva aprobada que bloquea, y asociar el error al campo `hora_inicio`; verificar en `python manage.py shell` que el mensaje contiene los tres datos y que la clave del error es `hora_inicio`.
- [ ] 1.3 Verificar la independencia de dimensiones y estados en `python manage.py shell`: 09:00–10:00 y 12:00–13:00 no lanzan error (contiguas), otro espacio u otra fecha no lanzan error, y reservas `PENDIENTE`, `RECHAZADA` y `CANCELADA` en 10:00–12:00 no bloquean una nueva solicitud idéntica.
- [ ] 1.4 Implementar `franjas_ocupadas(*, espacio, fecha)` que devuelva las reservas `APROBADA` del espacio y fecha ordenadas por `hora_inicio`, limitando los campos a hora de inicio y hora de fin (y el identificador si la plantilla lo necesita); verificar en `python manage.py shell` que excluye pendientes, rechazadas y canceladas y que no expone solicitante ni motivo.

## 2. Integración en creación y aprobación

- [ ] 2.1 Integrar `validar_disponibilidad` dentro de `crear_solicitud`, después de las validaciones existentes y dentro de `transaction.atomic`; verificar con una reserva aprobada de 10:00 a 12:00 que `crear_solicitud` para 11:00–13:00 lanza `ValidationError` y que el conteo de reservas no cambia.
- [ ] 2.2 Confirmar que el error de conflicto llega al formulario: `SolicitudReservaForm` debe quedar inválido con el mensaje del servicio asociado a `hora_inicio`; verificar en `python manage.py shell` que `form.errors["hora_inicio"]` contiene el mensaje con espacio, fecha y franja.
- [ ] 2.3 Implementar `aprobar_reserva(*, reserva, actor)` en `reservations/services.py` con `transaction.atomic`, recarga de la reserva con `select_for_update()`, exigencia de estado `PENDIENTE`, exigencia de rol `APROBADOR` o `ADMINISTRADOR`, revalidación con `validar_disponibilidad(..., excluir_reserva=reserva.pk)` y cambio de estado a `APROBADA`; verificar en `python manage.py shell` que una solicitud sin conflicto pasa a `APROBADA` y que un actor `SOLICITANTE` recibe `PermissionDenied`. `aprobar_reserva` es el nombre canónico que `aprobacion-rechazo` reutiliza y completa, sin renombrarlo.
- [ ] 2.4 Verificar la atomicidad del rechazo: con una reserva aprobada en conflicto, un intento de aprobación debe lanzar `ValidationError` y la solicitud debe seguir en `PENDIENTE` al recargarla desde la base; comprobar también que una reserva no pendiente no puede aprobarse.
- [ ] 2.5 Documentar en el docstring de `aprobar_reserva` la revalidación, la transacción y la limitación de `select_for_update` en SQLite; verificar que el docstring coincide con el comportamiento cubierto por las pruebas del grupo 5.

**Hito de la regla crítica:** los grupos 1 y 2 (validación, creación y aprobación) pueden
cerrarse y verificarse antes de implementar la vista de los grupos 3 y 4. La vista de
disponibilidad es una capacidad de consulta y no bloquea la regla de simultaneidad.

## 3. Vista de disponibilidad

- [ ] 3.1 Implementar `DisponibilidadForm(forms.Form)` en `reservations/forms.py` con `espacio` limitado a espacios activos y `fecha` de tipo fecha con valor inicial `timezone.localdate()`; verificar en `python manage.py shell` que un espacio inactivo no es una opción válida y que una fecha con formato inválido invalida el formulario.
- [ ] 3.2 Implementar `DisponibilidadView(LoginRequiredMixin, TemplateView)` en `reservations/views.py`: sin parámetros muestra solo el formulario, con parámetros válidos consulta `franjas_ocupadas` y las pasa al contexto, y con parámetros inválidos muestra los errores sin franjas; verificar con el cliente de pruebas los tres casos.
- [ ] 3.3 Agregar la ruta `reservas/disponibilidad/` con nombre `reservations:disponibilidad` en `reservations/urls.py`; verificar con `python manage.py check` y con `reverse("reservations:disponibilidad")` que apunta a `/reservas/disponibilidad/`.
- [ ] 3.4 Verificar el control de acceso de la vista: un anónimo es redirigido al login con `next` y un usuario autenticado de cualquier rol obtiene 200; comprobar con el cliente de pruebas.

## 4. Plantilla

- [ ] 4.1 Crear `reservations/templates/reservations/disponibilidad.html` con el formulario de espacio y fecha, la tabla de franjas ocupadas ordenadas y un mensaje explícito cuando no hay franjas; verificar que una fecha con una sola reserva aprobada muestra exactamente esa franja y que una fecha libre muestra el mensaje de disponibilidad.
- [ ] 4.2 Mostrar en la plantilla que solo se listan reservas aprobadas y enlazar de vuelta al listado de reservas y a la creación de una nueva solicitud; verificar que el texto aclara el criterio y que ambos enlaces resuelven.
- [ ] 4.3 Agregar un enlace a la consulta de disponibilidad desde `solicitud_lista.html` y desde la barra de navegación de `templates/base.html` para usuarios autenticados; verificar que un anónimo no ve el enlace y que un usuario autenticado navega sin errores.

## 5. Pruebas de la regla de disponibilidad

- [ ] 5.1 Ampliar `reservations/tests/utils.py` con helpers para crear reservas en un estado dado y para generar una reserva aprobada con franja concreta; verificar con `python manage.py test reservations` que el paquete se descubre sin errores.
- [ ] 5.2 Escribir `reservations/tests/test_disponibilidad.py` con la matriz de cruces contra una aprobada de 10:00–12:00: total, parcial al inicio, parcial al final, contenida, contenedora, contigua anterior, contigua posterior y un minuto de solapamiento; verificar con `python manage.py test reservations.tests.test_disponibilidad` (cubre REQ-DIS-001 y REQ-DIS-004).
- [ ] 5.3 Agregar a `test_disponibilidad.py` los casos de estados y dimensiones: aprobada bloquea; pendiente, rechazada y cancelada no bloquean; mismo horario en otro espacio y en otra fecha se acepta; verificar con `python manage.py test reservations.tests.test_disponibilidad` (cubre REQ-DIS-002 y REQ-DIS-005).
- [ ] 5.4 Agregar pruebas de límites horarios: contigüidad exacta en ambos sentidos, solapamiento de un minuto, franja que usa las 06:00 y las 22:00 del horario operativo y franja inmediatamente anterior o posterior al cierre; verificar con `python manage.py test reservations.tests.test_disponibilidad`.
- [ ] 5.5 Ampliar las pruebas de creación: `crear_solicitud` rechaza un cruce con aprobada sin crear fila, el mensaje incluye espacio, fecha y franja, y el formulario muestra el error en `hora_inicio`; verificar con `python manage.py test reservations.tests.test_services reservations.tests.test_forms` (cubre REQ-DIS-003 y REQ-DIS-009).
- [ ] 5.6 Ampliar las pruebas de aprobación: conflicto con aprobada deja `PENDIENTE`, conflicto creado después de la solicitud impide aprobar, dos pendientes que se cruzan permiten aprobar la primera y rechazan la segunda, una solicitud sin conflicto se aprueba, una solicitud no pendiente se rechaza y un actor sin rol no puede aprobar; verificar con `python manage.py test reservations.tests.test_services` (cubre REQ-DIS-006, REQ-DIS-007 y REQ-DIS-009).
- [ ] 5.7 Cerrar la regla crítica: ejecutar `python manage.py test reservations.tests.test_disponibilidad reservations.tests.test_services reservations.tests.test_forms` y `python manage.py makemigrations --check --dry-run`; verificar que la suite de la regla pasa sin depender de la vista de disponibilidad.

## 6. Pruebas de la vista de disponibilidad

- [ ] 6.1 Escribir las pruebas de la vista: lista solo franjas aprobadas y ordenadas, excluye pendientes/rechazadas/canceladas, fecha sin aprobadas muestra el mensaje de libre, parámetros inválidos muestran errores sin franjas, espacio inactivo inválido, anónimo redirigido al login con `next` y la consulta se recalcula tras aprobar una nueva reserva; verificar con `python manage.py test reservations.tests.test_views` (cubre REQ-DIS-008).
- [ ] 6.2 Ejecutar `python manage.py test` completo y `python manage.py check`; verificar que la suite pasa, que no hay migraciones pendientes ni nuevas, y que cada escenario de `specs/disponibilidad/spec.md` tiene al menos una prueba cuyo nombre incluye el identificador del requisito.

## Workflow follow-up

- Revisar los artefactos antes de implementar.
- Implementar después de `solicitud-reserva`.
- Tras las pruebas en verde, archivar el cambio para crear la especificación vigente de `disponibilidad`.
- Registrar para `aprobacion` que debe reutilizar `aprobar_reserva` (nombre canónico ya definido aquí), no duplicar la validación, y agregar vista, rechazo, cancelación y `HistorialReserva`.
- Registrar para el cierre que la mitigación de concurrencia depende de transacción y revalidación; documentar la limitación de SQLite en el informe final.
