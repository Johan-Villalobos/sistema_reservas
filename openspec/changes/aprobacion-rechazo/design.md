# Design

## Context

Ver `proposal.md` — Why. Este cambio se apoya en tres capacidades ya planificadas:

- `solicitud-reserva`: modelo `Reserva` con espacio, solicitante, fecha, hora de
  inicio, hora de fin, motivo, estado, `creado_en` y `actualizado_en`; enum
  `EstadoReserva` con `PENDIENTE`, `APROBADA`, `RECHAZADA` y `CANCELADA`; creación en
  `reservations/services.py`; detalle visible para el solicitante, aprobadores y
  administradores. Dejó diferidos `revisado_por` y `motivo_decision` para este cambio.
- `disponibilidad-simultaneidad`: `validar_disponibilidad(*, espacio, fecha,
  hora_inicio, hora_fin, excluir_reserva=None)`, `franjas_ocupadas` y una función
  `aprobar_reserva(*, reserva, actor)` introducida solo para verificar la
  revalidación al aprobar. Este cambio la reutiliza y la completa con la máquina de
  estados, el revisor, el motivo y `fecha_decision`; no la renombra.
- `usuarios-roles-permisos`: roles `SOLICITANTE`, `APROBADOR` y `ADMINISTRADOR`,
  `RolRequeridoMixin` con `roles_permitidos`, redirección al login para anónimos,
  `PermissionDenied` para roles no autorizados y plantilla `403.html`.

Restricciones del plan:

- Transiciones válidas de este incremento (2.5): `PENDIENTE → APROBADA` y
  `PENDIENTE → RECHAZADA`, solo para Aprobador o Administrador, con motivo en el
  rechazo. La cancelación pertenece al cambio siguiente.
- La aprobación debe revalidar el cruce dentro de una transacción atómica (2.6).
- SQLite no soporta bloqueo de filas (3.3); el riesgo R1 se mitiga con transacción,
  revalidación y pruebas específicas, y el R8 se documenta.

## Goals / Non-Goals

**Goals:**

- Cerrar el ciclo de vida de la solicitud con una decisión explícita, trazable y
  auditable a nivel de datos.
- Concentrar la máquina de estados y las reglas de decisión en servicios, para que la
  web solo traduzca errores.
- Ofrecer una cola de trabajo útil para aprobadores y administradores, sin exponer
  acciones a solicitantes ni permitir autodecisiones.
- Reutilizar la validación de disponibilidad, sin duplicar la regla de cruces.
- Cubrir con pruebas cada escenario y cada límite de acceso.

**Non-Goals:**

- No se implementa la cancelación por el solicitante ni la transición a `CANCELADA`.
- No se agrega `HistorialReserva`; solo se conserva la última decisión en la reserva.
- No se notifica por correo ni se incorporan tareas asíncronas.
- No hay aprobación o rechazo masivos, edición de solicitudes decididas ni
  reactivación de rechazadas.
- No se pagina la cola ni se agregan filtros por espacio o fecha.
- No se agregan índices, modelos adicionales ni cambios en la regla de cruces.
- No se resuelve el bloqueo pesimista real en SQLite.

## Decisions

### 1. Campos de decisión en `Reserva` y migración

`reservations/models.py` agrega:

| Campo | Tipo | Nota |
|---|---|---|
| `revisado_por` | `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name="reservas_revisadas")` | usuario que aprobó o rechazó |
| `motivo_decision` | `TextField(blank=True, default="")` | justificación del rechazo; vacío en una aprobación |
| `fecha_decision` | `DateTimeField(null=True, blank=True)` | instante de la aprobación o del rechazo |

Se genera `reservations/migrations/0002_...` con `AddField` para los tres campos. No hay
migración de datos: las reservas existentes quedan con `revisado_por=NULL`,
`motivo_decision=""` y `fecha_decision=NULL`, que es el estado coherente para
solicitudes aún no decididas.

- **Motivo**: `solicitud-reserva` ya había reservado `revisado_por` y
  `motivo_decision` para la aprobación. `SET_NULL` conserva la reserva si se elimina el
  usuario revisor; `PROTECT` impediría borrar cuentas y `CASCADE` perdería la reserva.
  `TextField` permite motivos largos sin imponer un límite que el plan no define.
- **`fecha_decision` propia**: se registra al aprobar o rechazar y es independiente de
  `creado_en` y `actualizado_en`. La cancelación actualiza `actualizado_en`, por lo que
  usar esa marca como fecha de decisión borraría el dato real.
- **Alternativa descartada**: usar `actualizado_en` como fecha de decisión. Cualquier
  cambio posterior de la reserva —en particular la cancelación— la sobrescribe y deja
  de reflejar cuándo se decidió.
- **Alternativa descartada**: `motivo_decision` obligatorio a nivel de base de datos.
  Las aprobaciones no llevan motivo; la obligatoriedad es condicional al rechazo y se
  valida en el servicio.

### 2. Máquina de estados y servicios de decisión

En `reservations/services.py`:

```text
TRANSICIONES_APROBACION = {
    (EstadoReserva.PENDIENTE, EstadoReserva.APROBADA),
    (EstadoReserva.PENDIENTE, EstadoReserva.RECHAZADA),
}

_decidir_reserva(*, reserva, actor, nuevo_estado, motivo_decision="")
aprobar_reserva(*, reserva, actor)
rechazar_reserva(*, reserva, actor, motivo)
```

`_decidir_reserva` es la única puerta de entrada y ejecuta, en este orden:

1. Abrir `transaction.atomic()`.
2. Exigir que `actor` esté autenticado y tenga rol `APROBADOR` o `ADMINISTRADOR`;
   en otro caso, `PermissionDenied`.
3. Recargar la reserva con `select_for_update()`.
4. Rechazar la autodecisión si `actor.pk == reserva.solicitante_id`; en otro caso,
   `PermissionDenied`.
5. Verificar que `(reserva.estado, nuevo_estado)` esté en
   `TRANSICIONES_APROBACION`; en otro caso, `ValidationError` con un mensaje que
   nombre el estado actual y la acción solicitada.
6. Si la transición es a `APROBADA`, bloquear el espacio y llamar a
   `validar_disponibilidad(..., excluir_reserva=reserva.pk)`.
7. Si la transición es a `RECHAZADA`, normalizar el motivo con `strip()` y rechazar
   vacío o compuesto solo por espacios con `ValidationError` en el campo `motivo`.
8. Actualizar de forma condicional con
   `Reserva.objects.filter(pk=reserva.pk, estado=EstadoReserva.PENDIENTE).update(...)`,
   fijando `estado`, `revisado_por`, `motivo_decision`, `fecha_decision` y
   `actualizado_en`.
9. Si la actualización afecta cero filas, otra transacción decidió primero:
   `ValidationError`("La solicitud ya fue decidida por otro usuario").
10. Recargar y devolver la reserva actualizada.

`aprobar_reserva` llama a `_decidir_reserva` con `APROBADA` y
`motivo_decision=""`. `rechazar_reserva` llama con `RECHAZADA` y el motivo recibido.

- **Motivo**: una sola función concentra la transacción, la autorización, la
  autodecisión y la transición; `aprobar_reserva` y `rechazar_reserva` quedan como API
  legible para las vistas y las pruebas.
- **Nombre canónico**: `aprobar_reserva` ya existe desde `disponibilidad`; este cambio
  la completa con la máquina de estados, el revisor, el motivo y `fecha_decision`. No
  se renombra ni se crea una segunda función de aprobación con reglas divergentes.
- **Motivo vacío en aprobación**: al aprobar se escribe `""` para no arrastrar un
  motivo de una decisión anterior. La máquina de estados impide redecidir, pero la
  limpieza mantiene el invariante.
- **Estado actual en el mensaje**: el error de transición incluye el estado actual
  ("La solicitud ya está aprobada" o "La solicitud está cancelada") para que la vista
  pueda mostrar un mensaje claro sin inspeccionar el modelo.
- **Alternativa descartada**: una función por transición con validaciones duplicadas.
  Permite que aprobar y rechazar diverjan en autorización o estado.
- **Alternativa descartada**: métodos `aprobar()`/`rechazar()` en el modelo. El
  proyecto concentra las reglas en `services.py` y el modelo quedaría acoplado a
  `validar_disponibilidad` y a los roles.
- **Alternativa descartada**: una librería de máquinas de estado. Añade dependencia
  para dos transiciones y un conjunto de estados pequeño.
- **Cancelación**: las transiciones `PENDIENTE → CANCELADA` y `APROBADA → CANCELADA`
  del plan 2.5 no se codifican aquí; pertenecen al cambio de cancelación, que deberá
  extender el mapa sin romper las dos transiciones actuales.

### 3. Transacción, bloqueo y concurrencia

La decisión completa ocurre en `transaction.atomic()`. Para la aprobación se bloquea
la fila del espacio con `EspacioAcademico.objects.select_for_update().get(pk=...)`
antes de revalidar. Así, en motores que soportan bloqueo de filas, dos aprobaciones
del mismo espacio se serializan y la segunda revalida contra la primera ya confirmada.

Además, la actualización condicional por `estado=PENDIENTE` actúa como defensa para la
carrera sobre la misma reserva: si dos aprobadores pulsan "Aprobar" a la vez, solo una
actualización afecta una fila; la otra recibe un error de "ya fue decidida" y no
sobrescribe al revisor.

Limitación de SQLite y mitigación:

1. `select_for_update()` se ignora en SQLite; no hay bloqueo pesimista real.
2. La transacción atómica, la recarga de la reserva y la revalidación inmediatamente
   antes de escribir reducen la ventana de carrera.
3. La actualización condicional impide que dos decisiones sobre la misma reserva
   prosperen.
4. Las pruebas cubren la secuencia de dos solicitudes que se cruzan y la revalidación
   ante un conflicto creado después de la solicitud.
5. El bloqueo del espacio se conserva para que, al migrar a PostgreSQL (plan 3.3),
   funcione sin cambiar la lógica.

- **Riesgo residual**: en SQLite, dos transacciones que aprueban reservas distintas
  del mismo espacio y fecha podrían validar antes de que alguna escriba. La ventana es
  pequeña, el sistema es de un solo proceso académico y el plan ya documenta R8. La
  solución definitiva es PostgreSQL con bloqueo de filas; queda fuera de alcance.
- **Trade-off del bloqueo por espacio**: serializa aprobaciones de fechas distintas en
  el mismo espacio. Es aceptable para el volumen previsto y evita bloqueos más
  complejos por franja.
- **Alternativa descartada**: restricción `EXCLUDE` en base de datos. SQLite no la
  soporta y requeriría modelar la franja como rango, decisión ajena a este cambio.
- **Alternativa descartada**: bloqueo global en memoria. No coordina múltiples
  procesos y añade estado compartido innecesario.

### 4. Prohibición de autodecisión — decisión nueva a confirmar en la revisión

Un usuario no puede aprobar ni rechazar una solicitud de la que sea solicitante,
aunque tenga rol `APROBADOR` o `ADMINISTRADOR`. La regla se aplica en dos capas:

- `reservations/permissions.py` expone
  `puede_decidir_reserva(usuario, reserva)`: verdadero si el usuario está autenticado,
  tiene rol `APROBADOR` o `ADMINISTRADOR` y no es el solicitante. No incluye el estado
  de la reserva: el estado es una regla de negocio que produce un mensaje de
  transición, no un 403.
- El servicio vuelve a comprobarlo con `PermissionDenied`, para que una llamada
  directa o una vista futura no evada la regla.

En la web, la comprobación fallida produce 403. En la cola, la solicitud propia se
muestra con una indicación de "No puedes decidir sobre tu propia solicitud" y sin
botones de acción, para que otro aprobador pueda decidirla.

- **Motivo**: evita el conflicto de interés evidente y coincide con la práctica
  institucional de separar quien solicita de quien autoriza.
- **Esta decisión no proviene de `PLAN_INGENIERIA.md`**; el plan solo exige que la
  aprobación la haga un Aprobador o Administrador. Se registra aquí para confirmarla
  en la revisión de especificaciones.
- **Si la revisión la rechaza**: se elimina la comparación con `solicitante_id` en el
  helper y en el servicio, y se ajustan las pruebas de autodecisión. No cambia el
  modelo ni las vistas.
- **Alternativa descartada**: permitir que un administrador decida su propia
  solicitud como excepción. Rompe la simetría de la regla y concentra el conflicto de
  interés en el rol con más privilegios.
- **Alternativa descartada**: solo impedir la autoaprobación y permitir el
  autorrechazo. El conflicto de interés existe en ambas direcciones y el rechazo
  también altera el resultado.

### 5. Permisos y respuestas HTTP

Las tres rutas nuevas usan `RolRequeridoMixin` con
`roles_permitidos = [Rol.APROBADOR, Rol.ADMINISTRADOR]`. El mixin redirige al login a
un anónimo con `next` y devuelve 403 a un autenticado sin rol. La autodecisión se
comprueba con `puede_decidir_reserva` y produce 403.

| Situación | Respuesta |
|---|---|
| Anónimo en cualquier ruta nueva | 302 al login con `next` |
| `SOLICITANTE` en cualquier ruta nueva | 403 |
| `APROBADOR`/`ADMINISTRADOR` decidiendo su propia solicitud | 403 |
| Reserva inexistente | 404 |
| GET sobre la ruta de aprobación | 405 |
| Aprobar o rechazar una reserva no `PENDIENTE` | 200 con mensaje de error y sin cambios |
| Aprobar con conflicto de disponibilidad | 200 con el mensaje del servicio y sin cambios |

- **Motivo**: separar autorización (403/404/405) de reglas de negocio (mensaje de
  transición) hace que las pruebas y los mensajes sean inequívocos. Un estado no
  pendiente no es un problema de permisos: el usuario puede ver la solicitud y la
  operación simplemente ya no es válida.
- **Alternativa descartada**: 409 Conflict para estados no pendientes o conflictos de
  disponibilidad. Es semánticamente correcto, pero el proyecto usa formularios HTML y
  respuestas 200 con errores; introducir 409 solo en estas rutas complica el cliente
  de pruebas y la UX sin aportar al requisito.
- **Alternativa descartada**: 404 para ocultar la existencia de solicitudes ajenas.
  Los aprobadores y administradores ya pueden ver cualquier detalle según
  `solicitud-reserva`; el 403 comunica el rechazo sin fingir inexistencia.

### 6. Vistas y rutas

| Ruta | Nombre | Vista | Métodos | Acceso |
|---|---|---|---|---|
| `reservas/pendientes/` | `reservations:pendientes` | `ReservaPendienteListView` | GET | `APROBADOR`, `ADMINISTRADOR` |
| `reservas/<int:pk>/aprobar/` | `reservations:aprobar` | `AprobarReservaView` | POST | `APROBADOR`, `ADMINISTRADOR`, no autodecisión |
| `reservas/<int:pk>/rechazar/` | `reservations:rechazar` | `RechazarReservaView` | GET, POST | `APROBADOR`, `ADMINISTRADOR`, no autodecisión |

- **Cola**: `ReservaPendienteListView(ListView)` con
  `Reserva.objects.filter(estado=EstadoReserva.PENDIENTE).select_related("espacio",
  "solicitante").order_by("fecha", "hora_inicio", "creado_en", "pk")`. El contexto
  incluye cada reserva con un indicador de si el usuario puede decidirla, para que la
  plantilla oculte las acciones de las solicitudes propias. Sin resultados, muestra un
  estado vacío.
- **Aprobación**: `AprobarReservaView(View)` con `http_method_names = ["post"]`.
  `post()` obtiene la reserva con `get_object_or_404`, comprueba
  `puede_decidir_reserva` y llama a `aprobar_reserva`. En éxito, redirige a
  `reservations:pendientes` con un mensaje de confirmación. Si el servicio lanza
  `ValidationError`, vuelve a renderizar `solicitud_detalle.html` con la reserva y el
  mensaje en el contexto, sin cambiar el estado.
- **Rechazo**: `RechazarReservaView(FormView)` con
  `form_class = RechazarReservaForm` y `template_name =
  "reservations/solicitud_rechazar.html"`. En `dispatch()` obtiene la reserva y
  comprueba el permiso de autodecisión; en `form_valid()` llama a `rechazar_reserva`.
  En éxito, redirige a `reservations:pendientes` con confirmación; si el servicio
  lanza `ValidationError` por estado, agrega el error al formulario y responde 200.
- **Detalle**: `SolicitudDetailView` existente sigue mostrando el detalle; la
  plantilla se amplía con los datos de decisión. No se agregan acciones al detalle
  para no duplicar la cola; la aprobación y el rechazo se ejecutan desde
  `reservations:pendientes`.
- **URLs**: se agregan a `reservations/urls.py` antes o después del detalle; los
  patrones con segmentos adicionales no colisionan con `<int:pk>/`.

### 7. Plantillas y navegación

- `reservations/templates/reservations/solicitud_pendientes.html`: tabla con espacio,
  solicitante, fecha, franja, motivo y acciones. Cada fila decidible tiene un formulario
  POST con `{% csrf_token %}` para aprobar y un enlace al formulario de rechazo. La
  fila propia muestra la indicación de autodecisión y no ofrece acciones. Estado vacío
  explícito. Los mensajes de éxito y error se muestran con el sistema de mensajes.
- `reservations/templates/reservations/solicitud_rechazar.html`: resumen de la
  solicitud (espacio, solicitante, fecha, franja, motivo original), formulario con el
  campo de motivo, errores por campo y no de campo, y botones de confirmar y cancelar.
- `solicitud_detalle.html`: agrega una sección de decisión con el estado, el revisor
  (nombre completo o username) y, si existe, el motivo con `linebreaksbr` para
  conservar saltos de línea. En estado `PENDIENTE` no muestra revisor ni motivo.
- `templates/base.html`: agrega el enlace "Pendientes" solo para usuarios
  autenticados con rol `APROBADOR` o `ADMINISTRADOR`. Un `SOLICITANTE` y un anónimo no
  ven el enlace.

- **Motivo**: mantener el patrón Bootstrap y de plantillas por aplicación del resto del
  proyecto; sin JavaScript, la cola y el rechazo son verificables con el cliente de
  pruebas.
- **Alternativa descartada**: aprobar con un enlace GET. Cambiaría estado en una
  petición no idempotente y permitiría aprobaciones por prefetch o crawlers. La acción
  es POST y CSRF.
- **Alternativa descartada**: un modal de rechazo en la cola. Añade JavaScript y
  complica las pruebas; una página de formulario es suficiente.

### 8. Formulario de rechazo

`reservations/forms.py` agrega `RechazarReservaForm(forms.Form)`:

- `motivo`: `CharField` obligatorio, `strip=True`, `widget=Textarea` con
  `rows=4` y clase Bootstrap.
- `clean_motivo()` vuelve a normalizar y rechaza el valor vacío después de `strip()`,
  con un mensaje explícito.
- No impone longitud máxima: el plan no define un límite para `motivo_decision` y el
  campo es `TextField`. Si la revisión decide un tope, se agrega al formulario, al
  servicio y a las pruebas sin cambiar el modelo.

- **Motivo**: un `Form` simple evita exponer campos del modelo y deja la regla de
  obligatoriedad en un solo lugar, reutilizada por la vista y por el servicio.
- **Alternativa descartada**: `ModelForm` de `Reserva`. Permitiría modificar estado o
  revisor si se descuidan los campos excluidos; un formulario de un solo campo es más
  seguro.
- **Alternativa descartada**: validar solo en el servicio y mostrar el error como no
  de campo. El requisito pide un motivo obligatorio y el error debe quedar junto al
  campo para que la corrección sea inmediata.

### 9. Pruebas

`reservations/tests/test_aprobacion.py` con clases separadas por capa:

- **Servicios**: aprobación válida, administrador, registro de revisor y
  `fecha_decision`, motivo vacío en aprobación; rechazo con motivo, motivo vacío, solo
  espacios y normalización; aprobar/rechazar estados no pendientes; autodecisión;
  actor sin rol o anónimo; conflicto de disponibilidad; conflicto creado después de la
  solicitud; dos pendientes que se cruzan; rechazo de una solicitud en conflicto;
  actualización condicional y estado sin cambios tras un fallo. Se comprueba además que
  `fecha_decision` no cambia al actualizar otros campos de una reserva ya decidida.
- **Vistas**: cola con solo pendientes y orden correcto, estado vacío, 403 de
  `SOLICITANTE`, redirección de anónimo; aprobación POST, 405 en GET, 404, 403 por
  autodecisión, 403 de `SOLICITANTE`, mensaje de conflicto y estado sin cambios;
  rechazo GET/POST, motivo vacío y solo espacios, estado no pendiente, 403 y
  redirección de anónimo.
- **Detalle**: el solicitante ve estado, revisor y motivo cuando existe; una solicitud
  pendiente no muestra datos de decisión; otro solicitante recibe 403.
- **Trazabilidad**: cada prueba incluye el identificador `REQ-APR-00X` en su nombre o
  en un docstring, y cada escenario de `specs/aprobacion-rechazo/spec.md` tiene al
  menos una prueba.

Se usan fechas futuras relativas y `setUpTestData` para no depender de la hora de
ejecución. Las pruebas de concurrencia real con hilos no se escriben porque SQLite las
hace no deterministas; se prueba la secuencia equivalente y se documenta la
limitación. Se ejecutan `python manage.py test`, `python manage.py check` y
`python manage.py makemigrations --check --dry-run`.

## Risks / Trade-offs

- **Carrera entre dos aprobaciones de reservas distintas del mismo espacio** →
  bloqueo del espacio en PostgreSQL, transacción y revalidación; en SQLite queda el
  riesgo residual documentado (R1/R8). Se prueba la secuencia y no hilos.
- **Doble decisión sobre la misma reserva** → actualización condicional por
  `estado=PENDIENTE`; la segunda operación falla con un mensaje claro y no sobrescribe
  al revisor.
- **La autodecisión es una regla nueva** → marcada para confirmación; si se rechaza,
  el cambio se limita al helper, al servicio y a las pruebas.
- **`fecha_decision` nula en reservas anteriores** → las reservas creadas antes de la
  migración no tienen decisión; se muestra "sin decisión" y el campo queda `NULL` hasta
  que se decidan. La cancelación no lo sobrescribe.
- **Sin `HistorialReserva`** → solo se conserva la última decisión en la reserva, con
  `revisado_por`, `motivo_decision` y `fecha_decision`. Es suficiente para este
  incremento; la trazabilidad completa llega con el cambio de cancelación e historial.
- **Motivo de rechazo sin límite de longitud** → aceptable para uso interno; si se
  necesita un tope, se agrega en un cambio posterior con su requisito y pruebas.
- **La cola no se pagina** → volumen académico previsto bajo; se puede agregar sin
  cambiar los requisitos.
- **Sin índice por estado, fecha y hora de inicio** → la cola filtra por `PENDIENTE` y
  ordena por fecha y hora. Con el volumen previsto es aceptable; si crece, se agrega un
  índice en un cambio con migración y medición.
- **Sin notificación al solicitante** → el solicitante ve la decisión al abrir su
  listado o detalle; el correo queda fuera de alcance.
- **403 en autodecisión revela la existencia de la solicitud** → solo para usuarios
  autenticados con rol privilegiado que ya pueden ver el detalle; aceptado.
- **El estado se puede manipular por ORM fuera del servicio** → la máquina de estados
  vive en `services.py`; una escritura directa puede saltarla. Se acepta la misma
  limitación que en los cambios previos y se cubre el camino soportado con pruebas.

## Migration Plan

1. Confirmar que `solicitud-reserva` y `disponibilidad-simultaneidad` están
   implementados y con la suite en verde.
2. Agregar `revisado_por`, `motivo_decision` y `fecha_decision` a `Reserva`; generar
   `reservations/migrations/0002_...`, aplicar `migrate` y verificar que las reservas
   existentes conservan `NULL`, cadena vacía y `NULL`.
3. Implementar `_decidir_reserva` y completar `aprobar_reserva` y `rechazar_reserva`;
   reutilizar el nombre `aprobar_reserva` ya definido en `disponibilidad`, sin
   renombrarlo.
4. Agregar `puede_decidir_reserva`, las vistas, las rutas y el formulario de rechazo.
5. Crear las plantillas de cola y rechazo; ampliar el detalle y la navegación.
6. Escribir y ejecutar la suite; ejecutar `check` y `makemigrations --check --dry-run`.

**Rollback**: revertir el código y aplicar la migración inversa de `0002`, que elimina
los tres campos. Si la base contiene decisiones reales, hacer `dumpdata` antes del
rollback (R5); en desarrollo, las solicitudes de prueba se pueden descartar. No hay
datos sembrados que dependan de estos campos.

## Open Questions

- **Confirmar la prohibición de autodecisión**: es una decisión nueva, no incluida en
  `PLAN_INGENIERIA.md`. Si la revisión prefiere que un administrador pueda decidir su
  propia solicitud, se ajustan `puede_decidir_reserva`, el servicio y las pruebas.
- **Confirmar que no se impone un máximo al motivo de rechazo**: el plan no define
  longitud para `motivo_decision`. Si se requiere un tope, se agrega al formulario, al
  servicio y a la especificación.
- **Confirmar el nombre y la semántica de `fecha_decision`**: es un campo propio,
  distinto de `creado_en` y `actualizado_en`, para que la cancelación no borre el
  instante real de la decisión. Si la revisión prefiere otro nombre, se ajusta la
  migración, el servicio, la especificación y las pruebas.
