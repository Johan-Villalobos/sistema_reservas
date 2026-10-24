# Design

## Context

Ver `proposal.md` — Why. Este cambio se apoya en tres cambios previos que aún no
están implementados y hereda sus convenciones:

- `base-proyecto`: `reservations/services.py` reservado para las reglas de negocio,
  plantilla base y `seed_data` en `core`.
- `usuarios-roles-permisos`: `accounts.Usuario` con roles `SOLICITANTE`,
  `APROBADOR` y `ADMINISTRADOR`, y el mecanismo `RolRequeridoMixin`.
- `gestion-espacios`: `spaces.EspacioAcademico` con `activo`, `TipoEspacio` y la
  recomendación de usar `on_delete=PROTECT` desde reservas hacia espacios.

Restricciones del plan 2.4–2.6:

- La reserva se compone de espacio, solicitante, fecha, hora de inicio, hora de fin,
  motivo y estado, con `hora_fin > hora_inicio`.
- Los estados del ciclo de vida son `PENDIENTE`, `APROBADA`, `RECHAZADA` y
  `CANCELADA`; la detección de solapamientos pertenece a una capacidad posterior.
- `USE_TZ` está activo y la zona del sistema es `America/Bogota`.

## Goals / Non-Goals

**Goals:**

- Garantizar en servicio y en base de datos la coherencia de la franja y la
  integridad de la creación.
- Dejar el modelo y el servicio listos para que `disponibilidad` y `aprobación`
  agreguen reglas sin reescribir la creación.
- Cubrir con pruebas cada validación y cada regla de visibilidad.

**Non-Goals:**

- No se detectan solapamientos ni se consulta disponibilidad; dos solicitudes
  `PENDIENTE` para la misma franja y espacio pueden coexistir en este cambio.
- No se aprueban, rechazan ni cancelan reservas; no se implementan transiciones de
  estado ni `HistorialReserva`.
- No se listan solicitudes ajenas para aprobadores; solo el detalle individual.
- No se agregan reservas de ejemplo a `seed_data`.
- No se pagina el listado ni se filtra por estado o fecha.
- No se admiten franjas que crucen la medianoche ni reservas de varios días.

## Decisions

### 1. Modelo `Reserva` con una fecha y dos horas

`reservations/models.py`:

| Campo | Tipo | Nota |
|---|---|---|
| `espacio` | `ForeignKey("spaces.EspacioAcademico", on_delete=PROTECT, related_name="reservas")` | conserva historial |
| `solicitante` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="reservas_solicitadas")` | tomado de la sesión |
| `fecha` | `DateField()` | única para inicio y fin |
| `hora_inicio` | `TimeField()` | |
| `hora_fin` | `TimeField()` | |
| `motivo` | `CharField(max_length=255)` | obligatorio |
| `estado` | `CharField(max_length=10, choices=EstadoReserva.choices, default=EstadoReserva.PENDIENTE)` | enum completo del plan |
| `creado_en` | `DateTimeField(auto_now_add=True)` | fecha de creación exigida |
| `actualizado_en` | `DateTimeField(auto_now=True)` | auditoría para cambios futuros |

`Meta` incluye `ordering = ["-fecha", "-hora_inicio"]` y
`CheckConstraint(check=Q(hora_fin__gt=F("hora_inicio")), name="ck_reserva_hora_fin_mayor")`.

- **Motivo**: una sola `fecha` hace estructuralmente imposible una franja de varios
  días; el requisito de "mismo día" se cumple por diseño y no solo por validación.
- **Estado completo ahora**: `EstadoReserva` define los cuatro valores del plan para
  no alterar `choices` con una migración en el cambio de aprobación. Este cambio solo
  escribe `PENDIENTE`; las transiciones se implementan después.
- **Campos diferidos**: `revisado_por`, `motivo_decision` y `fecha_decision` pertenecen
  a la aprobación y se agregan allí con una migración nullable. Incluirlos ahora sin
  usarlos crearía campos muertos y decisiones de UI prematuras.
- **Alternativa descartada**: dos `DateTimeField` (inicio y fin). Haría posible cruzar
  días y obligaría a validar la misma fecha con dos fuentes de verdad.
- **Alternativa descartada**: borrado en cascada del espacio o del usuario. Rompería
  el historial; `PROTECT` lo impide.

`Usuario` y `EspacioAcademico` se referencian por `settings.AUTH_USER_MODEL` y por
cadena de app, respectivamente, para evitar importaciones circulares.

`estado` se escribe únicamente en `crear_solicitud` en este cambio. Las transiciones
posteriores (`aprobar_reserva`, `rechazar_reserva`, `cancelar_reserva`) también viven
en `reservations/services.py`; las vistas y formularios nunca asignan `estado`
directamente (REQ-SOL-011). SQLite no puede impedir una escritura directa por ORM, por
lo que esa vía se documenta como no soportada y no se presenta como garantía de base
de datos.

### 2. Reglas en `reservations/services.py`

Se implementan dos funciones:

- `validar_solicitud(*, espacio, fecha, hora_inicio, hora_fin, motivo, ahora=None)`:
  aplica todas las reglas y lanza `ValidationError` con un diccionario cuyas claves
  coinciden con los campos del formulario.
- `crear_solicitud(*, espacio, solicitante, fecha, hora_inicio, hora_fin, motivo)`
  con `@transaction.atomic`: revalida, vuelve a comprobar que el espacio siga activo
  y crea la reserva con `estado=PENDIENTE`.

Reglas de `validar_solicitud`:

1. `hora_fin > hora_inicio` (mensaje asociado a `hora_fin`).
2. Motivo normalizado con `strip()` no vacío y de longitud ≤ 255.
3. Espacio con `activo=True`; se consulta de nuevo en base dentro de la transacción
   para no confiar en una instancia cargada antes del POST.
4. Inicio combinado `fecha + hora_inicio`, consciente de zona horaria, no anterior a
   `ahora`; `ahora` por defecto es `timezone.localtime()` y es inyectable en pruebas.
5. Franja dentro de `[HORARIO_OPERATIVO_INICIO, HORARIO_OPERATIVO_FIN]`, con ambos
   extremos inclusivos.

`crear_solicitud` recibe `solicitante` y no acepta `estado`: el estado inicial no es
parametrizable.

- **Motivo**: REQ-BAS-007 exige que las reglas vivan en la capa de servicios; la vista
  y el formulario solo traducen errores.
- **Alternativa descartada**: validar en `Model.clean()` y llamar `full_clean()` desde
  la vista. Mezcla la regla con la persistencia y hace difícil probar mensajes y
  límites horarios.
- **Doble validación**: el formulario llama a `validar_solicitud` en `clean()` para
  mostrar los errores junto a cada campo, y `crear_solicitud` vuelve a validar dentro
  de la transacción para cubrir cambios entre la carga del formulario y el POST. La
  regla está una sola vez; solo se invoca dos veces.
- **`ahora` inyectable**: evita parchear `timezone.now` en las pruebas y hace
  deterministas los casos de "hoy con hora pasada" y los límites de medianoche.

### 3. Horario operativo configurable — decisión nueva a confirmar en la revisión

`config/settings.py` declara:

```text
HORARIO_OPERATIVO_INICIO = "06:00"
HORARIO_OPERATIVO_FIN = "22:00"
```

`reservations/services.py` los lee con `time.fromisoformat` y lanza
`ImproperlyConfigured` si el valor no es una hora válida o si inicio ≥ fin. Los
límites son inclusivos: 06:00 y 22:00 se aceptan.

- **Motivo**: REQ-SOL-007 pide un parámetro configurable y el plan no define horario
  operativo. Un par de cadenas ISO en `settings` es legible, no requiere dependencias
  y permite `override_settings` en pruebas.
- **Esta decisión no proviene del plan y queda sujeta a confirmación en la revisión**
  de especificaciones: el valor inicial 06:00–22:00 y la inclusividad de los extremos
  son supuestos razonables para una institución, pero la institución podría operar
  otro rango o excluir el cierre.
- **Alternativa descartada**: horario fijo en código. Impide ajustar el rango sin
  tocar lógica y contradice el requisito.
- **Alternativa descartada**: horario por espacio en la base de datos. Añade un campo
  y un CRUD que el requisito no pide; puede llegar en un cambio posterior.
- **Alternativa descartada**: objetos `datetime.time` directamente en settings. Son
  válidos, pero las cadenas ISO son más fáciles de leer y de sobrescribir en pruebas.

### 4. Formulario único de solicitud

`SolicitudReservaForm(ModelForm)` expone `espacio`, `fecha`, `hora_inicio`,
`hora_fin` y `motivo`; excluye `solicitante`, `estado` y campos de auditoría.

- `espacio`: queryset limitado a `EspacioAcademico.objects.activos()` ordenado por
  nombre. Un identificador inactivo enviado manualmente falla la validación de
  opción y, aun así, el servicio lo rechaza.
- `fecha`, `hora_inicio` y `hora_fin`: widgets HTML5 (`type="date"` y `type="time"`)
  con clases de Bootstrap.
- `clean()`: llama a `validar_solicitud` con los datos del formulario y deja que el
  `ValidationError` con diccionario se asocie a los campos correspondientes.
- Los campos de auditoría y el estado nunca se aceptan desde el cliente.

- **Motivo**: reutilizar el servicio evita duplicar reglas y garantiza mensajes
  idénticos entre la interfaz y la API interna.
- **Trade-off**: el formulario hace una consulta adicional para comprobar el espacio;
  es irrelevante con SQLite local y aporta mensajes claros.

### 5. Vistas y visibilidad

| Ruta | Nombre | Vista | Acceso |
|---|---|---|---|
| `reservas/` | `reservations:solicitud_lista` | `SolicitudListView` | autenticado, solo propias |
| `reservas/nueva/` | `reservations:solicitud_crear` | `SolicitudCreateView` | autenticado |
| `reservas/<int:pk>/` | `reservations:solicitud_detalle` | `SolicitudDetailView` | solicitante, `APROBADOR` o `ADMINISTRADOR` |

- **Listado**: `LoginRequiredMixin`; queryset
  `Reserva.objects.filter(solicitante=request.user).select_related("espacio")`. No
  pagina ni filtra; el volumen esperado es bajo.
- **Creación**: `LoginRequiredMixin`; `form_valid` llama a `crear_solicitud` con
  `solicitante=request.user`; si el servicio lanza `ValidationError`, se agrega al
  formulario y se responde 200 con errores; si crea, redirige al detalle.
- **Detalle**: `LoginRequiredMixin` y comprobación en `dispatch` con
  `puede_ver_solicitud(usuario, reserva)`; si no, `PermissionDenied` (403).

`reservations/permissions.py` expone `puede_ver_solicitud(usuario, reserva)`:
verdadero si el usuario está autenticado y es el solicitante o tiene rol
`APROBADOR`/`ADMINISTRADOR`.

- **Motivo**: la visibilidad por objeto no se expresa con el mecanismo de roles de
  `accounts`; el helper evita duplicar la condición y servirá al listado de
  aprobación futuro.
- **403 en lugar de 404**: el requisito dice que el detalle solo es visible para
  ciertos roles; 403 comunica el rechazo y es coherente con el resto del sistema. Se
  acepta que confirma la existencia de la reserva a un usuario autenticado.
- **Alternativa descartada**: reutilizar `RolRequeridoMixin` para el detalle. Dejaría
  fuera al solicitante, que no tiene rol privilegiado.
- **Alternativa descartada**: listar todas las solicitudes al administrador. El
  requisito limita el listado a las propias; los aprobadores obtendrán su cola de
  trabajo en el cambio de aprobación.

### 6. Plantillas y navegación

- `solicitud_lista.html`: tabla con espacio, fecha, franja, estado y enlace al
  detalle, más botón "Nueva solicitud" y estado vacío.
- `solicitud_form.html`: formulario con errores por campo, ayuda del horario
  operativo y botones de enviar y cancelar.
- `solicitud_detalle.html`: espacio, solicitante, fecha, franja, motivo, estado y
  fecha de creación; botón de volver.
- `templates/base.html`: el enlace "Reservas" ya previsto pasa a
  `{% url 'reservations:solicitud_lista' %}`.

- **Motivo**: mantener el patrón Bootstrap y de plantillas por aplicación del resto
  del proyecto.
- **Alternativa descartada**: componentes con JavaScript. No aportan al alcance y
  dificultan las pruebas de servidor.

### 7. `seed_data` no siembra reservas

No se agregan reservas de ejemplo: dependen de espacios y usuarios con fechas
futuras, y una reserva sembrada interferiría con las validaciones de disponibilidad
del cambio siguiente. `seed_data` conserva su comportamiento actual.

- **Motivo**: evitar datos que envejezcan (fechas pasadas) y conflictos artificiales.
- **Alternativa descartada**: sembrar reservas relativas a `timezone.now()`. Hace el
  comando menos predecible y no lo pide ningún requisito.

### 8. Pruebas: una validación, un escenario

`reservations/tests/`:

- `utils.py`: helpers `crear_espacio`, `crear_usuario`, `datos_solicitud` con fechas
  futuras relativas.
- `test_models.py`: valores por defecto, `__str__`, relación con espacio y
  solicitante, y `CheckConstraint` mediante inserción directa que debe lanzar
  `IntegrityError`.
- `test_forms.py`: campos expuestos, solo espacios activos en el selector, motivo
  vacío/255/256, hora igual/menor, y errores mapeados a campos.
- `test_services.py`: creación válida (estado, solicitante, `creado_en`), estado
  enviado ignorado, espacio inactivo, fecha de ayer, hora transcurrida hoy con `ahora`
  inyectado, horario 05:59/06:00/22:00/22:01 y `override_settings` con otro horario.
- `test_views.py`: creación autenticada, anónimo redirigido en crear/listar/detalle,
  listado solo con solicitudes propias, detalle 200 para dueño/aprobador/administrador,
  403 para otro solicitante y 404 para un identificador inexistente.

Se usan fechas de mañana para los casos válidos y de ayer para el pasado, de modo que
la suite no dependa de la hora exacta de ejecución; los límites horarios usan `ahora`
inyectado.

- **Motivo**: el plan 5.3 exige una prueba por escenario con el identificador del
  requisito. Separar modelo, formulario, servicio y vistas localiza el fallo.
- **Alternativa descartada**: probar solo a través de la vista. No distingue si falla
  la restricción SQL, la regla del servicio o el mapeo del formulario.

### 9. Dependencia con disponibilidad y aprobación

`disponibilidad` deberá:

- Añadir la comprobación de solapamiento dentro de `crear_solicitud` y en la
  aprobación, dentro de una transacción, reutilizando la firma actual del servicio.
- Decidir si las solicitudes `PENDIENTE` bloquean o no; el plan 2.6 indica que solo
  las `APROBADA` bloquean.
- Agregar las pruebas de concurrencia y la revalidación al aprobar.

`aprobación` deberá agregar `revisado_por`, `motivo_decision`, `HistorialReserva` y
las transiciones válidas sobre `EstadoReserva`.

- **Motivo**: mantener una única puerta de entrada a la creación evita que las reglas
  de disponibilidad se implementen en dos lugares.
- **Trade-off**: durante este cambio pueden existir solicitudes duplicadas para la
  misma franja; es un estado intermedio esperado y queda documentado.

## Risks / Trade-offs

- **Dependencia de tres cambios previos** → se implementa al final de la secuencia;
  sin `accounts` y `spaces` no existen usuarios ni espacios. Se registra como
  precondición en `tasks.md`.
- **Horario operativo no definido en el plan** → valor inicial 06:00–22:00 con
  extremos inclusivos, configurable y marcado para confirmación en la revisión. Si la
  institución cambia el rango, solo se ajusta el setting y las pruebas de límites.
- **Sin detección de solapamientos** → solicitudes duplicadas son posibles. Se mitiga
  con la dependencia explícita de `disponibilidad`, que debe implementarse antes de
  usar el sistema en producción.
- **Zona horaria** → la comparación con "ahora" usa `timezone.localtime()` y
  `make_aware` con la zona activa; Bogotá no tiene horario de verano, lo que reduce el
  riesgo. Las pruebas inyectan `ahora` para evitar flakiness.
- **Estado manipulado por ORM** → el enum completo existe desde ahora y las
  transiciones se aplican en `reservations/services.py`; una escritura directa por ORM
  podría fijar otro estado. SQLite no ofrece una restricción que lo impida, así que se
  documenta como vía no soportada (REQ-SOL-011). El servicio y el formulario no la
  permiten.
- **Consulta de espacio dentro de la transacción** → SQLite no bloquea filas; una
  desactivación concurrente podría colarse. Limitación conocida (R8) y aceptada para
  el alcance académico.
- **Listado sin paginación** → suficiente para el volumen previsto; se puede agregar
  sin cambiar requisitos.
- **Motivo de 255 caracteres visibles en tablas** → se trunca en el listado y se
  muestra completo en el detalle.

## Migration Plan

1. Confirmar que `base-proyecto`, `usuarios-roles-permisos` y `gestion-espacios` están
   implementados y con la suite en verde.
2. Crear `reservations/models.py` con `EstadoReserva`, `Reserva`, `Meta` y la
   restricción de horas.
3. Generar `reservations/migrations/0001_initial.py` y aplicar `migrate`; verificar la
   tabla, las claves foráneas `PROTECT` y el `CHECK`.
4. Agregar `HORARIO_OPERATIVO_INICIO` y `HORARIO_OPERATIVO_FIN` a
   `config/settings.py`; implementar `reservations/services.py` y
   `reservations/permissions.py`.
5. Implementar `forms.py`, `views.py`, `urls.py`, incluirlas en `config/urls.py` y
   actualizar la navegación de `base.html`.
6. Crear las plantillas de listado, formulario y detalle.
7. Escribir la suite `reservations/tests/` y ejecutar `python manage.py test` completa.

**Rollback**: revertir el commit, eliminar la migración y la tabla de reservas, y
restaurar el enlace de navegación. No hay datos que preservar porque `seed_data` no
crea reservas; las solicitudes creadas manualmente en desarrollo se pierden, lo cual
es aceptable en esta etapa.

## Open Questions

- **Confirmar en la revisión de especificaciones**: el horario operativo inicial
  06:00–22:00, con apertura y cierre inclusivos, es una decisión nueva que no figura
  en `PLAN_INGENIERIA.md` (REQ-SOL-007). Si la revisión define otro rango u otra
  política de bordes, cambia el valor del setting y las pruebas de límites, sin
  alterar el diseño del servicio.
- Fuera de este cambio y sin impacto en sus requisitos: si las solicitudes
  `PENDIENTE` deben bloquear el espacio o solo las `APROBADA`, decisión que pertenece
  a `disponibilidad` (el plan 2.6 ya sugiere que solo las aprobadas bloquean).
