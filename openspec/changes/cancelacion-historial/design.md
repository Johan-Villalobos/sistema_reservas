# Design

## Context

Ver `proposal.md` — Why. Este cambio cierra las transiciones que
`aprobacion-rechazo` dejó explícitamente diferidas y agrega la trazabilidad que el
plan 2.4 reservó para `HistorialReserva`. Se apoya en las capacidades ya planificadas:

- `solicitud-reserva`: `Reserva` con espacio, solicitante, fecha, `hora_inicio`,
  `hora_fin`, motivo, `estado`, `creado_en` y `actualizado_en`; `EstadoReserva` con
  `PENDIENTE`, `APROBADA`, `RECHAZADA` y `CANCELADA`; `crear_solicitud` decorada con
  `transaction.atomic`; detalle visible para el solicitante, aprobadores y
  administradores.
- `disponibilidad-simultaneidad`: `validar_disponibilidad(*, espacio, fecha,
  hora_inicio, hora_fin, excluir_reserva=None)` y `franjas_ocupadas(*, espacio,
  fecha)`. Solo las reservas `APROBADA` bloquean; por eso cambiar el estado a
  `CANCELADA` libera la franja sin borrar ni modificar la reserva.
- `aprobacion-rechazo`: `aprobar_reserva(*, reserva, actor)`,
  `rechazar_reserva(*, reserva, actor, motivo)`, `_decidir_reserva`,
  `puede_decidir_reserva`, `revisado_por`, `motivo_decision` y `fecha_decision`;
  migración `0002`. Su diseño dejó la cancelación y `HistorialReserva` para este
  cambio.
- `solicitud-reserva`: `REQ-SOL-011` establece que las transiciones de estado solo se
  ejecutan en `reservations/services.py`. `cancelar_reserva` cumple esa regla y la
  cancelación no escribe `estado` desde la vista.
- `usuarios-roles-permisos`: roles `SOLICITANTE`, `APROBADOR` y `ADMINISTRADOR`,
  `RolRequeridoMixin`, redirección al login para anónimos y `PermissionDenied` (403).

Restricciones del plan:

- `HistorialReserva` tiene reserva, estado anterior, estado nuevo, actor,
  `fecha_evento` y observación (2.4).
- Las transiciones válidas de cancelación son `PENDIENTE → CANCELADA` y
  `APROBADA → CANCELADA`, para el solicitante o un administrador (2.5).
- La cancelación de una aprobada debe dejar el espacio disponible para esa franja
  (REQ-CAN-005); la regla de solapamiento solo considera `APROBADA` (2.6).
- Cada escenario de aceptación debe convertirse en al menos una prueba automatizada
  con el identificador del requisito (5.3).
- SQLite no implementa bloqueo de filas; `select_for_update()` se ignora (3.3, R8).

## Goals / Non-Goals

**Goals:**

- Agregar `HistorialReserva` y su migración sin alterar `Reserva`.
- Implementar una cancelación autorizada, acotada por estado y por hora de inicio, y
  consistente con la liberación de disponibilidad.
- Registrar cada transición (creación, aprobación, rechazo y cancelación) en la misma
  transacción atómica que el cambio de estado.
- Hacer el historial inmutable desde la aplicación y ofrecer su consulta con alcance
  por usuario y filtros útiles.
- Cubrir con pruebas cada escenario, cada límite temporal y cada control de acceso.

**Non-Goals:**

- No se exige un motivo de cancelación ni se agrega un formulario con ese campo; el
  servicio acepta una observación opcional para uso interno o futuro.
- No se editan, restauran ni reactivan reservas canceladas o rechazadas.
- No se notifica por correo ni se agregan tareas asíncronas.
- No se pagina el historial ni se define retención o archivado.
- No se implementan disparadores de base de datos para inmutabilidad; las garantías
  son de aplicación (modelo, queryset y administración).
- No se rellenan eventos históricos para reservas creadas antes de este cambio.
- No se resuelve el bloqueo pesimista real en SQLite.
- No se cambia la regla de cruces ni el comportamiento de aprobación y rechazo, salvo
  la escritura del evento de historial.

## Decisions

### 1. Modelo `HistorialReserva` y migración `0003`

`reservations/models.py` agrega:

| Campo | Tipo | Nota |
|---|---|---|
| `reserva` | `ForeignKey("Reserva", on_delete=PROTECT, related_name="historial")` | conserva la reserva y su rastro |
| `estado_anterior` | `CharField(max_length=10, choices=EstadoReserva.choices, null=True, blank=True)` | `NULL` representa la creación |
| `estado_nuevo` | `CharField(max_length=10, choices=EstadoReserva.choices)` | estado resultante |
| `actor` | `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name="eventos_reserva")` | usuario que ejecutó la transición |
| `fecha_evento` | `DateTimeField(default=timezone.now, editable=False)` | instante del evento |
| `observacion` | `TextField(blank=True, default="")` | motivo del rechazo o nota opcional |

`Meta` define `ordering = ["fecha_evento", "pk"]` e índices por
`("reserva", "fecha_evento")`, `("estado_nuevo",)` y `("fecha_evento",)`. La migración
`reservations/migrations/0003_historialreserva.py` depende de `0002` de
`aprobacion-rechazo`, crea el modelo y sus índices. No hay migración de datos: el
historial empieza con los eventos posteriores al despliegue.

- **Motivo**: `NULL` en `estado_anterior` distingue la creación sin inventar un estado
  falso y permite consultar `estado_anterior__isnull=True`; un centinela como `""`
  obligaría a documentar un valor que no pertenece al enum.
- **`PROTECT` en `reserva` y `actor`**: el historial es auditoría; `CASCADE` lo
  borraría con la reserva o el usuario y `SET_NULL` perdería al actor. Las cuentas se
  desactivan con `activo` y no se eliminan; una reserva con historial tampoco se
  elimina. Si en el futuro se exige borrar usuarios, habrá que agregar una instantánea
  del nombre del actor antes de cambiar la política.
- **`fecha_evento` con `default=timezone.now` en lugar de `auto_now_add`**: permite
  inyectar el mismo instante usado para `actualizado_en` y hace deterministas las
  pruebas y una eventual importación. `editable=False` evita exponerlo en formularios.
- **Sin `CheckConstraint` de estados**: `choices` valida en formularios y el servicio
  controla las transiciones; una restricción `IN` duplicaría el enum en la base y
  obligaría a una migración por cada estado nuevo.
- **Sin `unique`**: una reserva tiene varios eventos a lo largo de su ciclo de vida.
- **Índices**: el detalle filtra por reserva y ordena por fecha; el listado filtra por
  estado y fecha. Con el volumen académico previsto son suficientes; no se indexa
  `actor` porque no es un filtro del requisito.
- **Sin relleno histórico**: las reservas existentes en desarrollo no tienen actor ni
  decisión verificables para reconstruir sus eventos. El plan no lo pide y un evento
  inventado sería peor que la ausencia. El repositorio es greenfield y los cambios
  previos son solo planificación, así que no hay datos que migrar.

`__str__` devuelve una representación legible, por ejemplo
`"<reserva> · PENDIENTE → APROBADA"` o `"<reserva> · Creación → PENDIENTE"`.

### 2. Servicio de cancelación y reglas de estado y tiempo

En `reservations/services.py`:

```text
TRANSICIONES_CANCELACION = {
    (EstadoReserva.PENDIENTE, EstadoReserva.CANCELADA),
    (EstadoReserva.APROBADA, EstadoReserva.CANCELADA),
}

cancelar_reserva(*, reserva, actor, ahora=None, observacion="")
motivo_no_cancelable(*, reserva, ahora=None) -> str | None
reserva_es_cancelable(*, reserva, ahora=None) -> bool
```

`cancelar_reserva` ejecuta, en este orden, dentro de `transaction.atomic()`:

1. Exigir que `actor` esté autenticado; en otro caso, `PermissionDenied`.
2. Recargar la reserva con
   `Reserva.objects.select_for_update().select_related("espacio").get(pk=reserva.pk)`.
3. Autorizar con `puede_cancelar_reserva(actor, reserva)`; en otro caso,
   `PermissionDenied`. La regla es: administrador o solicitante de la reserva.
4. Verificar que `(reserva.estado, CANCELADA)` esté en
   `TRANSICIONES_CANCELACION`; en otro caso, `ValidationError` con un mensaje que
   nombre el estado actual.
5. Calcular el inicio combinando `reserva.fecha` y `reserva.hora_inicio` en la zona
   horaria activa. Si `ahora >= inicio`, `ValidationError` ("la reserva ya inició").
6. Bloquear el espacio con
   `EspacioAcademico.objects.select_for_update().get(pk=reserva.espacio_id)` para
   serializar, en motores que lo soportan, con una aprobación concurrente del mismo
   espacio.
7. Actualizar de forma condicional, escribiendo solo `estado` y `actualizado_en`:
   `Reserva.objects.filter(pk=reserva.pk, estado=estado_original).update(estado=CANCELADA, actualizado_en=ahora)`.
   La actualización SHALL NOT incluir `fecha_decision`: si la reserva estaba
   `APROBADA` conserva el instante en que se decidió, y una reserva `PENDIENTE`
   cancelada conserva `fecha_decision=None`. Si afecta cero filas, otra operación
   cambió la reserva: `ValidationError`
   ("la reserva cambió de estado; vuelva a intentarlo").
8. Crear el evento con `_registrar_historial(...)` usando `estado_anterior=estado_original`,
   `estado_nuevo=CANCELADA`, `actor`, `observacion` y `fecha_evento=ahora`.
9. Recargar y devolver la reserva.

`motivo_no_cancelable` devuelve `None` si la reserva está en `PENDIENTE` o `APROBADA`
y `ahora < inicio`; en caso contrario devuelve un mensaje específico:
"La reserva ya está cancelada", "La reserva fue rechazada", "La reserva ya inició" o
"El estado no permite cancelar". `reserva_es_cancelable` es
`motivo_no_cancelable(...) is None`. Las vistas usan ambas funciones para decidir si
muestran el botón y para explicar por qué no está disponible, sin duplicar la regla.

- **Motivo**: la autorización, el estado y el tiempo son reglas distintas; devolver
  mensajes específicos permite que la vista explique el bloqueo sin inspeccionar el
  modelo y mantiene una sola fuente de verdad.
- **Frontera temporal**: se rechaza cuando `ahora >= inicio`. El requisito dice "cuya
  hora de inicio ya pasó"; se interpreta que, a partir del inicio inclusive, la
  reserva ya comenzó y no debe cancelarse. Es una decisión explícita, marcada en
  Open Questions; si la institución prefiere permitir el instante exacto, se cambia
  la comparación a `ahora > inicio` y sus pruebas.
- **Actualización condicional por el estado original**: si la reserva cambió de
  `PENDIENTE` a `APROBADA` entre la lectura y la escritura, la cancelación no se
  aplica silenciosamente sobre una versión obsoleta. El usuario puede reintentar; el
  nuevo estado sigue siendo cancelable si la hora no pasó.
- **Bloqueo del espacio**: en PostgreSQL serializa la cancelación con una aprobación
  del mismo espacio y evita que una aprobación valide una franja que se está
  liberando. En SQLite se ignora; la actualización condicional y la transacción
  reducen la ventana, pero queda el riesgo residual R8.
- **No se reutiliza `_decidir_reserva`**: la autorización (dueño o administrador, sin
  la prohibición de autodecisión), la regla temporal y la observación son distintas de
  las de aprobación/rechazo. Compartir la función mezclaría dos máquinas de decisión;
  se comparte el registro de historial y el patrón transaccional.
- **Observación opcional**: la vista no pide un motivo porque el requisito no lo
  exige; pasa `observacion=""`. El servicio queda preparado para que un cambio futuro
  agregue un campo sin modificar el modelo ni la transacción.
- **`fecha_decision` se preserva**: la cancelación no es una decisión de aprobación ni
  de rechazo, así que no debe reescribir ese campo. Escribir solo `estado` y
  `actualizado_en` mantiene la fecha real de la decisión y evita que la cancelación
  borre trazabilidad, algo que sí ocurría si se usaba `actualizado_en` como
  aproximación. La transición `APROBADA → CANCELADA` queda registrada en el historial
  con su propio `fecha_evento`.
- **Alternativa descartada**: cancelar con `reserva.save()`. `auto_now` y los campos
  actualizables permiten sobrescribir más de lo necesario; `update()` condicional
  limita la escritura a estado y fecha y deja `fecha_decision` intacta.
- **Alternativa descartada**: borrar la reserva al cancelar. Perdería el rastro y
  contradice el estado `CANCELADA` del plan.
- **Transiciones de estado solo en servicios**: `cancelar_reserva` es la única vía
  soportada para pasar a `CANCELADA` (REQ-SOL-011). SQLite no impide una escritura
  directa por ORM; esa vía se documenta como no soportada y no se presenta como
  garantía de base de datos.

### 3. Historial compartido y atomicidad

```text
_registrar_historial(*, reserva, estado_anterior, estado_nuevo, actor,
                     observacion="", fecha_evento=None)
```

Crea un `HistorialReserva` con `HistorialReserva.objects.create(...)`. Es privado:
solo los servicios de `reservations` escriben historial. Antes de crear, comprueba
`connection.in_atomic_block`; si no hay transacción activa, lanza `RuntimeError` para
impedir un evento huérfano. No abre una transacción propia ni captura excepciones:
el llamador ya está dentro de `transaction.atomic()`.

Integración:

| Servicio | Estado anterior | Estado nuevo | Actor | Observación | `fecha_evento` |
|---|---|---|---|---|---|
| `crear_solicitud` | `None` | `PENDIENTE` | `solicitante` | `""` | `reserva.creado_en` |
| `_decidir_reserva` (aprobar) | `PENDIENTE` | `APROBADA` | `actor` | `""` | `ahora` |
| `_decidir_reserva` (rechazar) | `PENDIENTE` | `RECHAZADA` | `actor` | `motivo_decision` | `ahora` |
| `cancelar_reserva` | `PENDIENTE` o `APROBADA` | `CANCELADA` | `actor` | `observacion` | `ahora` |

`crear_solicitud` ya es atómica; se agrega la llamada después de crear la reserva.
`_decidir_reserva` calcula `ahora = timezone.now()` al inicio, lo usa para
`actualizado_en` y para el evento, y llama al helper solo después de que la
actualización condicional afectó una fila. `cancelar_reserva` hace lo propio. Las
funciones públicas `aprobar_reserva` y `rechazar_reserva` aceptan `ahora=None`
opcional y lo reenvían, para pruebas deterministas; el valor por defecto no cambia la
API existente.

- **Motivo**: una única función concentra el formato del evento y el guard de
  transacción; los servicios solo indican la transición.
- **Atomicidad**: si `HistorialReserva.objects.create` falla, la excepción sale del
  bloque atómico y Django revierte la creación o la actualización de estado. No se
  captura dentro del servicio; las vistas solo capturan `ValidationError` de negocio,
  no errores de base. Un fallo de auditoría produce 500 y rollback, en lugar de un
  cambio de estado sin rastro.
- **Observación del rechazo**: se copia el motivo ya normalizado a la observación.
  Aunque `motivo_decision` vive en la reserva y podría cambiar en el futuro, el evento
  conserva el motivo original de forma inmutable.
- **Sin evento en transiciones fallidas**: el helper se llama después de la
  actualización condicional exitosa; si la transición o la actualización fallan, no se
  llega a él.
- **`connection.in_atomic_block`**: es una comprobación defensiva barata que evita
  usar el helper desde una vista o un script sin transacción. No sustituye la prueba
  de rollback; la complementa.
- **Alternativa descartada**: señales `post_save` sobre `Reserva`. Se disparan también
  en escrituras que no son transiciones, no conocen al actor ni la observación y
  dificultan la atomicidad explícita.
- **Alternativa descartada**: un método `Reserva.cambiar_estado()` que escriba el
  historial. Acopla el modelo a roles, disponibilidad y servicios; el proyecto
  concentra las reglas en `services.py`.

### 4. Inmutabilidad desde la aplicación

`reservations/models.py` define un queryset y un manager propios:

```text
class HistorialReservaQuerySet(models.QuerySet):
    def delete(self): ...
    def update(self, **kwargs): ...
    def bulk_update(self, objs, fields, batch_size=None): ...

class HistorialReservaManager(models.Manager.from_queryset(HistorialReservaQuerySet)):
    pass
```

`HistorialReserva` usa `objects = HistorialReservaManager()` y sobrescribe:

- `save()`: si `not self._state.adding`, lanza `ValidationError` ("los registros de
  historial son inmutables"). Las inserciones nuevas siguen permitidas.
- `delete()`: lanza `ValidationError`. El borrado individual y el borrado en cascada
  quedan bloqueados.
- `QuerySet.delete()`, `QuerySet.update()` y `QuerySet.bulk_update()`: lanzan
  `ValidationError`; impiden la edición o el borrado masivo aunque no pasen por
  `save()`.
- `refresh_from_db()` no se altera; solo lee.

La administración de Django registra el modelo con
`has_add_permission=False`, `has_change_permission=False`, `has_delete_permission=False`
y `has_view_permission=True`, campos de solo lectura y filtros de consulta. Así un
administrador puede inspeccionar el historial, pero no alterarlo ni borrarlo.

- **Motivo**: el requisito habla de inmutabilidad "desde la aplicación"; modelo,
  queryset y admin cubren las vías normales de Django sin depender de un motor.
- **Límite**: SQL crudo, `connection.cursor()` o un `QuerySet._raw_delete()` interno
  pueden saltarse estas guardas. Una garantía total exigiría disparadores o permisos
  de base de datos, fuera del alcance y no portables entre SQLite y PostgreSQL. Se
  documenta y se prueba el camino soportado.
- **`PROTECT`**: impide borrar una reserva o un actor con historial. Es coherente con
  la auditoría y con `Reserva.solicitante`/`espacio`, que ya usan `PROTECT`.
- **Alternativa descartada**: solo `save()` y `delete()` del modelo. Un
  `QuerySet.update()` editaría sin pasar por `save()`.
- **Alternativa descartada**: una tabla de auditoría externa o `django-simple-history`.
  Agrega dependencia y un modelo distinto del que define el plan 2.4.

### 5. Permisos y respuestas HTTP

`reservations/permissions.py` agrega:

- `es_administrador(usuario)`: autenticado y rol `ADMINISTRADOR`.
- `puede_cancelar_reserva(usuario, reserva)`: autenticado y (administrador o
  `reserva.solicitante_id == usuario.pk`). No incluye estado ni tiempo: esas son
  reglas de negocio que producen un mensaje, no un 403.
- `puede_ver_historial(usuario, reserva)`: autenticado y (administrador o
  solicitante). Un `APROBADOR` no propietario no obtiene historial, aunque
  `puede_ver_solicitud` le permita ver el detalle.

El servicio vuelve a comprobar `puede_cancelar_reserva` después de recargar la
reserva, para que una llamada directa no evada la regla. La vista comprueba antes de
renderizar o ejecutar.

| Situación | Respuesta |
|---|---|
| Anónimo en cancelación o historial | 302 al login con `next` |
| Autenticado no propietario ni administrador en cancelación | 403 |
| Reserva inexistente en cancelación | 404 |
| GET de confirmación de cancelación | 200 con resumen y advertencia |
| POST de cancelación exitoso | 302 al detalle con mensaje de éxito |
| Estado `RECHAZADA` o `CANCELADA` | 200 con error y sin cambios |
| Reserva ya iniciada | 200 con error y sin cambios |
| Cambio concurrente del estado | 200 con error y sin cambios |
| Fallo al guardar historial | 500 y rollback; no se oculta el fallo de auditoría |
| Historial: usuario autenticado | 200 con su alcance |
| Historial: administrador | 200 con todos los eventos |

- **Motivo**: separar 403/404 de los errores de negocio mantiene mensajes
  inequívocos, igual que en `aprobacion-rechazo`.
- **403 en cancelación ajena**: el requisito lo exige explícitamente. Se acepta que
  confirma la existencia de la reserva a un usuario autenticado; el detalle ya es
  visible para aprobadores y administradores.
- **El historial no responde 403 por reserva**: no hay ruta por reserva; el listado se
  filtra por solicitante y el detalle oculta la sección. Así un solicitante no puede
  inferir eventos ajenos.
- **Alternativa descartada**: 404 para ocultar reservas ajenas. Contradice el 403
  pedido y el comportamiento del detalle.

### 6. Vistas y rutas

| Ruta | Nombre | Vista | Métodos | Acceso |
|---|---|---|---|---|
| `reservas/historial/` | `reservations:historial` | `HistorialReservaListView` | GET | autenticado; alcance por usuario |
| `reservas/<int:pk>/cancelar/` | `reservations:cancelar` | `CancelarReservaView` | GET, POST | solicitante o administrador |

Se agregan a `reservations/urls.py`; `historial/` se declara antes de `<int:pk>/` por
legibilidad, aunque el convertidor `int` no colisiona con la cadena.

`CancelarReservaView(LoginRequiredMixin, View)`:

- `dispatch()` obtiene la reserva con
  `get_object_or_404(Reserva.objects.select_related("espacio", "solicitante"), pk=pk)`;
  si `puede_cancelar_reserva` es falso, lanza `PermissionDenied`.
- `get()` calcula `motivo = motivo_no_cancelable(reserva=reserva)` y renderiza
  `solicitud_cancelar.html` con `reserva`, `motivo` y `puede_confirmar = motivo is None`.
- `post()` llama a `cancelar_reserva(reserva=reserva, actor=request.user)`. En éxito,
  agrega un mensaje y redirige a `reservations:solicitud_detalle`. Si el servicio lanza
  `ValidationError`, vuelve a renderizar la confirmación con el error y estado 200, sin
  cambios.
- No acepta un campo de motivo; el formulario es solo un botón de confirmación con
  `{% csrf_token %}`.

`HistorialReservaListView(LoginRequiredMixin, ListView)`:

- `get_queryset()` parte de
  `HistorialReserva.objects.select_related("reserva", "reserva__espacio", "reserva__solicitante", "actor")`.
  Si el usuario no es administrador, filtra por
  `reserva__solicitante=request.user`; el administrador no filtra. Ordena por
  `-fecha_evento`, `-pk`.
- `_filtros()` lee `request.GET`:
  - `estado`: si está en `EstadoReserva.values`, filtra `estado_nuevo`; si no, se
    ignora.
  - `fecha`: si `datetime.date.fromisoformat` la acepta, filtra
    `fecha_evento__date=fecha`; si no, se ignora.
  - `espacio`: si es entero y existe un `EspacioAcademico` con ese `pk`, filtra
    `reserva__espacio_id`; si no, se ignora.
  - Los filtros se combinan con AND y se aplican después del alcance por usuario.
- `get_context_data()` expone `historial`, `filtros` (solo valores válidos, para que el
  formulario sea sticky), `estados = EstadoReserva.choices` y `espacios` (todos los
  espacios ordenados por nombre, para el selector). Si no hay resultados, la plantilla
  muestra un estado vacío.

- **Motivo**: una sola ruta de historial con alcance por queryset evita rutas por
  reserva y reduce el riesgo de fuga; los filtros manuales permiten ignorar valores
  inválidos sin mostrar errores, tal como pide el requisito.
- **Fecha local**: `fecha_evento__date` usa la zona activa (`America/Bogota`,
  `USE_TZ=True`). Bogotá no tiene horario de verano, lo que reduce ambigüedades; un
  cambio de zona requeriría revisar las pruebas de fecha.
- **Espacios en el selector**: se muestran todos, incluso inactivos, porque el
  historial puede referenciar espacios que ya no están activos. El alcance por
  solicitante se aplica antes del filtro.
- **Sin paginación**: el volumen previsto es bajo y el requisito no la pide. Se puede
  agregar después sin cambiar la especificación.
- **Detalle**: `SolicitudDetailView` conserva `puede_ver_solicitud`; agrega al
  contexto `puede_ver_historial`, `historial` (solo si el usuario puede verlo, con
  `select_related("actor")` y orden ascendente), `puede_ver_cancelacion` y
  `motivo_no_cancelable`. Un aprobador no propietario sigue viendo el detalle, pero no
  la sección de historial ni la acción de cancelar.
- **Alternativa descartada**: una ruta `reservas/<pk>/historial/`. Duplica la lógica de
  permisos y permite intentos de acceso directo a historial ajeno; el detalle y el
  listado cubren la consulta.
- **Alternativa descartada**: filtrar con un `Form` y mostrar errores. El requisito
  pide ignorar valores inválidos, no rechazarlos; el parseo manual mantiene la página
  útil ante enlaces viejos o manipulados.

### 7. Plantillas y navegación

- `reservations/templates/reservations/historial_lista.html`: formulario GET con
  `estado` (select), `fecha` (`type="date"`) y `espacio` (select), botón de filtrar y
  enlace para limpiar. Tabla con fecha/hora del evento, reserva (espacio, fecha y
  franja), transición (`anterior → nuevo`, con "Creación" si el anterior es nulo),
  actor (nombre completo o username), observación con `linebreaksbr` y enlace al
  detalle. Estado vacío explícito. Una nota indica si se está viendo el historial
  propio o el de todas las reservas.
- `solicitud_cancelar.html`: resumen de la reserva (espacio, solicitante, fecha,
  franja, motivo y estado), advertencia de que la cancelación es definitiva, mensaje
  de error si el servicio rechazó la operación, y botones de confirmar y volver. Si
  `puede_confirmar` es falso, el botón de confirmar no se muestra y se explica el
  motivo.
- `solicitud_detalle.html`: agrega, solo si `puede_ver_cancelacion`, un botón
  "Cancelar reserva" cuando `motivo_no_cancelable` es nulo, o el motivo cuando no lo
  es. Agrega, solo si `puede_ver_historial`, una sección de historial con tabla
  ascendente y estado vacío; incluye un enlace al listado completo. No muestra nada
  nuevo al aprobador no propietario.
- `solicitud_lista.html`: se mantiene sin acciones por fila para evitar consultas por
  reserva; la cancelación se inicia desde el detalle, que ya es el punto de
  confirmación. Si se quisiera un acceso directo, se agregaría una anotación de
  "cancelable" en el queryset en un cambio posterior.
- `templates/base.html`: agrega el enlace "Historial" para cualquier usuario
  autenticado; "Pendientes" sigue visible solo para `APROBADOR` y `ADMINISTRADOR`.
  Anónimos no ven ninguno.

- **Motivo**: mantener el patrón Bootstrap y de plantillas por aplicación, sin
  JavaScript, para que todo sea verificable con el cliente de pruebas.
- **Alternativa descartada**: cancelar con un enlace GET. Cambiaría estado en una
  petición no idempotente; la confirmación es GET y la ejecución POST con CSRF.
- **Alternativa descartada**: un modal de cancelación en el detalle. Añade JavaScript y
  complica las pruebas; una página de confirmación es suficiente.

### 8. Pruebas y trazabilidad

`reservations/tests/` agrega:

- `test_cancelacion.py`: servicios, vistas, permisos y liberación de disponibilidad.
- `test_historial.py`: modelo, inmutabilidad, registro en las cuatro transiciones,
  atomicidad, listado, detalle y filtros.
- Se amplía `reservations/tests/utils.py` con helpers de reservas e historial y fechas
  relativas; se revisan `test_services.py` y `test_aprobacion.py` para que sigan en
  verde con la escritura de historial.

Cobertura por requisito:

| Requisito | Casos principales |
|---|---|
| `REQ-CAN-001` | cancelación propia `PENDIENTE` y `APROBADA`, aprobador propietario, datos conservados, `fecha_decision` intacta tras cancelar una aprobada, botón visible solo si es cancelable |
| `REQ-CAN-002` | administrador cancela ajena `PENDIENTE` y `APROBADA`, cancela la propia, ve la acción en el detalle ajeno |
| `REQ-CAN-003` | rechazada, ya cancelada, administrador sobre ambas, vista 200 sin cambios |
| `REQ-CAN-004` | un minuto antes, instante exacto, después del inicio, fecha pasada, vista sin cambios |
| `REQ-CAN-005` | disponibilidad libre, segunda solicitud aprobable, `franjas_ocupadas`, pendiente sin efecto |
| `REQ-CAN-006` | 403 de otro solicitante, 403 de aprobador, servicio directo, anónimo, 404 |
| `REQ-HIS-001` | creación, aprobación, rechazo con observación, cancelación, transición inválida sin evento |
| `REQ-HIS-002` | fallo de historial en cancelación, creación y aprobación; rollback y cero eventos |
| `REQ-HIS-003` | `save()` de existente, `delete()`, borrado masivo, `update()`/`bulk_update()`, inserción permitida, admin de solo lectura |
| `REQ-HIS-004` | solicitante solo propio, administrador todo, filtro que no amplía alcance, aprobador sin historial ajeno, detalle, anónimo |
| `REQ-HIS-005` | estado, fecha, espacio, combinación, valores inválidos, sticky |

Detalles de implementación de las pruebas:

- Las fechas válidas usan `timezone.now() + timedelta(days=2)`; las pasadas,
  `- timedelta(days=2)`. Los límites exactos se prueban en el servicio con
  `ahora=inicio`, sin depender del reloj.
- La atomicidad se prueba con
  `mock.patch("reservations.services.HistorialReserva.objects.create", side_effect=IntegrityError(...))`
  y se afirma que el estado y el conteo de historial no cambian. Se agrega una prueba
  que parchea `_registrar_historial` para verificar que la excepción atraviesa el
  bloque atómico.
- La concurrencia real con hilos no se prueba porque SQLite la hace no determinista;
  se prueba la secuencia equivalente y la actualización condicional. Se documenta la
  limitación R8.
- La cancelación de una reserva `APROBADA` con `fecha_decision` registrada se prueba
  comparando el valor antes y después: debe permanecer idéntico y solo cambiar
  `estado` y `actualizado_en`. Una reserva `PENDIENTE` cancelada conserva
  `fecha_decision=None`.
- Cada prueba incluye `REQ-CAN-00X` o `REQ-HIS-00X` en el nombre o en un docstring, y
  cada escenario de `specs/cancelacion-historial/spec.md` tiene al menos una prueba.
- Se ejecutan `python manage.py test reservations`, `python manage.py test`,
  `python manage.py check` y `python manage.py makemigrations --check --dry-run`.

## Risks / Trade-offs

- **SQLite sin bloqueo de filas** → transacción, recarga, actualización condicional y
  bloqueo del espacio para PostgreSQL; riesgo residual documentado (R1/R8).
- **Inmutabilidad solo de aplicación** → modelo, queryset y admin cubren las vías
  normales; SQL crudo puede saltarlas. Se documenta y se prueba el camino soportado.
- **Estado escrito por ORM fuera del servicio** → `cancelar_reserva` es la única vía
  soportada a `CANCELADA` (REQ-SOL-011); SQLite no impide una escritura directa y esa
  vía se documenta como no soportada.
- **`PROTECT` en `actor`** → impide borrar usuarios con historial. Es coherente con la
  baja lógica por `activo`; si se exige borrado físico, habrá que agregar una
  instantánea del actor y migrar la política.
- **Historial sin relleno** → las reservas previas al despliegue no muestran eventos.
  El repositorio es greenfield y los cambios previos son planificación; si hubiera
  datos reales, se evaluaría una migración de datos con actor inferido.
- **Crecimiento del historial** → no hay paginación ni retención. El volumen
  académico previsto es bajo; se puede agregar sin cambiar requisitos.
- **Filtro por fecha y zona horaria** → `fecha_evento__date` depende de la zona activa.
  Bogotá no tiene horario de verano; un cambio de zona exige revisar las pruebas.
- **Frontera del inicio exacto** → se rechaza en el instante exacto. Es una decisión
  documentada; si la institución prefiere lo contrario, cambia una comparación y sus
  pruebas.
- **Cancelación sin motivo** → la observación queda vacía salvo que un futuro cambio
  agregue un campo. El actor y la fecha ya identifican la operación.
- **Fallo de historial bloquea la operación** → es intencional para no perder
  auditoría; operativamente exige aplicar la migración `0003` antes de usar creación,
  aprobación o cancelación.
- **Bloqueo del espacio** → puede serializar operaciones de fechas distintas del mismo
  espacio. Es aceptable para el volumen previsto y evita bloqueos por franja más
  complejos.
- **Admin de solo lectura** → no permite altas manuales de historial; los eventos solo
  nacen de los servicios. Es la garantía buscada, no una limitación funcional.

## Migration Plan

1. Confirmar que `solicitud-reserva`, `disponibilidad-simultaneidad` y
   `aprobacion-rechazo` están implementados y con la suite en verde.
2. Agregar `HistorialReserva` y sus guardas de inmutabilidad; generar
   `reservations/migrations/0003_historialreserva.py`, aplicar `migrate` y verificar
   tabla, claves foráneas `PROTECT` e índices.
3. Implementar `_registrar_historial` e integrarlo en `crear_solicitud` y
   `_decidir_reserva`; ejecutar las suites existentes para detectar regresiones.
4. Implementar `cancelar_reserva`, `motivo_no_cancelable`, `reserva_es_cancelable` y
   los helpers de permisos.
5. Agregar las vistas, rutas y plantillas de cancelación e historial; ampliar el
   detalle y la navegación.
6. Escribir y ejecutar la suite completa; ejecutar `check` y
   `makemigrations --check --dry-run`.

**Rollback**: revertir el código y aplicar la migración inversa de `0003`, que elimina
la tabla de historial y sus índices. Es seguro porque ninguna otra tabla referencia a
`HistorialReserva`; se pierden los eventos, no las reservas. Si la base contiene
historial que se quiere conservar, hacer `dumpdata` antes del rollback (R5).

## Open Questions

- **Confirmar la frontera del inicio exacto**: se rechaza la cancelación cuando
  `ahora == inicio`. Si la revisión prefiere permitirla, se cambia a `ahora > inicio`
  y se ajustan las pruebas de `REQ-CAN-004`.
- **Confirmar que la cancelación no exige motivo**: el requisito no lo pide y la
  observación es opcional. Si se requiere, se agrega un campo al formulario, se valida
  en el servicio y se prueba; el modelo no cambia.
- **Confirmar que el `APROBADOR` no ve historial ajeno**: `REQ-HIS-004` solo otorga la
  consulta al solicitante y al administrador. Si la institución quiere que el
  aprobador audite lo que aprobó, se amplía `puede_ver_historial` y el alcance del
  listado, con sus pruebas.
- **Confirmar la ausencia de relleno histórico**: se asume un despliegue sin datos de
  producción. Si hay reservas previas que deben auditarse, se define una migración de
  datos con actor y fecha inferidos.
- **Confirmar la inmutabilidad solo de aplicación**: no se agregan disparadores de
  base de datos. Si la revisión exige una garantía a nivel de motor, se evaluará una
  migración específica por motor, fuera del alcance actual.
