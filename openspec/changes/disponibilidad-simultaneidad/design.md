# Design

## Context

Ver `proposal.md` — Why. Este cambio se implementa sobre `solicitud-reserva`, que ya
aporta el modelo `Reserva` (espacio, solicitante, fecha, hora de inicio, hora de fin,
motivo, estado), el enum `EstadoReserva` con los cuatro estados y `crear_solicitud`
en `reservations/services.py`. También hereda de `gestion-espacios` el catálogo y de
`usuarios-roles` los roles y el mecanismo de permisos.

El plan fija:

- La regla de solapamiento: `inicio_A < fin_B y fin_A > inicio_B` (2.6).
- Solo las reservas `APROBADA` bloquean el espacio (2.6).
- Al aprobar se revalida dentro de una transacción atómica (2.6).
- SQLite no soporta bloqueo de filas y `select_for_update` se ignora (3.3); el riesgo
  R1 se mitiga con transacción atómica, validación previa y pruebas específicas.

`solicitud-reserva` dejó fuera de alcance la aprobación y documentó que
`disponibilidad` debía extender `crear_solicitud` y decidir el efecto de las
solicitudes `PENDIENTE`. Este diseño resuelve ambas cosas.

## Goals / Non-Goals

**Goals:**

- Una sola función de validación, usada por creación y aprobación, con la misma
  semántica y el mismo mensaje.
- Evitar que la aprobación concurrente de dos solicitudes que se cruzan termine con
  dos reservas aprobadas.
- Ofrecer una consulta de disponibilidad simple y verificable, sin depender de
  JavaScript.
- Cubrir con pruebas la matriz completa de cruces y los límites exactos.

**Non-Goals:**

- No se implementa la pantalla de aprobación, el rechazo, la cancelación ni el
  historial; solo la transición mínima `PENDIENTE → APROBADA` a nivel de servicio.
- No se detectan conflictos entre solicitudes `PENDIENTE` al crearlas.
- No se genera una parrilla de franjas libres ni un calendario; se listan las franjas
  ocupadas.
- No se agregan índices, modelos, campos ni migraciones.
- No se resuelve el bloqueo pesimista real: SQLite no lo soporta.

## Decisions

### 1. Función única `validar_disponibilidad` en `reservations/services.py`

```text
validar_disponibilidad(*, espacio, fecha, hora_inicio, hora_fin, excluir_reserva=None)
```

Consulta:

```text
Reserva.objects.filter(
    espacio=espacio,
    fecha=fecha,
    estado=EstadoReserva.APROBADA,
    hora_inicio__lt=hora_fin,
    hora_fin__gt=hora_inicio,
).exclude(pk=excluir_reserva).order_by("hora_inicio").first()
```

Si encuentra una reserva, lanza `ValidationError` con la clave de campo
`hora_inicio` y un mensaje que incluye espacio, fecha y la franja ocupada:
"El espacio <nombre> ya está reservado el <fecha> de <inicio> a <fin>."

- **Motivo**: las desigualdades estrictas implementan literalmente la fórmula del
  plan y, de paso, permiten la contigüidad: si `fin_A == inicio_B`, la condición
  `hora_inicio__lt=hora_fin` no se cumple. El estado `APROBADA` en el filtro garantiza
  REQ-DIS-002 sin lógica adicional.
- **Un solo lugar**: creación y aprobación llaman a esta función; no hay consultas de
  conflicto en vistas ni en formularios.
- **`excluir_reserva`**: permite revalidar una reserva que ya existe sin que se
  considere a sí misma; en la aprobación se pasa su `pk`.
- **Instancia para el mensaje**: se limita a la primera reserva conflictiva ordenada
  por hora de inicio; no se listan todos los conflictos porque el mensaje debe ser
  accionable y el formulario solo necesita uno.
- **Alternativa descartada**: `filter(hora_inicio__range=...)`. No expresa
  correctamente los cruces parciales ni la contención.
- **Alternativa descartada**: comparar en Python tras traer todas las reservas. Costoso
  e inútil con el ORM.

### 2. Integración en `crear_solicitud`

Después de las validaciones de `solicitud-reserva` (horas, motivo, espacio activo,
pasado, horario operativo) y dentro del `transaction.atomic` existente, se llama a
`validar_disponibilidad` con el espacio, fecha y franja. Si hay conflicto, se propaga
el `ValidationError` y no se crea nada.

- **Motivo**: mantener el orden de validaciones hace que los errores de datos básicos
  tengan prioridad sobre el de disponibilidad; el chequeo ocurre dentro de la misma
  transacción de escritura.
- **Solicitudes `PENDIENTE`**: no bloquean, por lo que dos pendientes idénticas pueden
  coexistir. Es el comportamiento que fija REQ-DIS-002 y el plan 2.6, y se resuelve en
  la aprobación.
- **Alternativa descartada**: bloquear también las pendientes. Contradice el plan y
  convertiría cada solicitud en un bloqueo preventivo permanente mientras no se
  resuelva.

### 3. Aprobación mínima `aprobar_reserva` con revalidación transaccional

```text
aprobar_reserva(*, reserva, actor)
```

Pasos:

1. `transaction.atomic()`.
2. Recargar la reserva con `select_for_update()` (ver limitación en la decisión 4).
3. Exigir `estado == PENDIENTE`; en otro caso, `ValidationError` ("solo se pueden
   aprobar solicitudes pendientes").
4. Exigir que `actor` esté autenticado y tenga rol `APROBADOR` o `ADMINISTRADOR`;
   en otro caso, `PermissionDenied`.
5. Llamar a `validar_disponibilidad(..., excluir_reserva=reserva.pk)`.
6. Fijar `estado = APROBADA` y guardar con `update_fields=["estado", "actualizado_en"]`.

- **Motivo**: REQ-DIS-006 y REQ-DIS-007 exigen que la aprobación revalide y que la
  segunda de dos solicitudes en conflicto falle. Sin una función de aprobación no hay
  forma de verificar esos escenarios, y `solicitud-reserva` no la incluyó.
- **Nombre canónico**: la función se llama `aprobar_reserva` desde este cambio.
  `aprobacion-rechazo` la reutiliza y la completa con la máquina de estados, el
  revisor y el motivo de decisión, sin renombrarla.
- **Alcance acotado**: no se agrega vista, plantilla, `revisado_por`, `motivo_decision`
  ni historial. La capacidad `aprobacion` reutilizará esta función y agregará esos
  elementos; no debe duplicar la validación.
- **Liberar la franja**: este cambio no define cómo una reserva `APROBADA` deja de
  estarlo. El escenario de que una segunda solicitud pueda aprobarse tras liberarse la
  primera pertenece a `cancelacion-historial` (REQ-CAN-005).
- **Comprobación de rol en el servicio**: defensa en profundidad. La vista de
  aprobación futura seguirá usando `RolRequeridoMixin`; el servicio no confía en que
  la capa web ya validó.
- **Estado previo**: al lanzar la excepción dentro de `atomic`, cualquier cambio
  parcial se revierte y la solicitud permanece `PENDIENTE`.

### 4. Limitación de SQLite y mitigación de la condición de carrera

`select_for_update()` se ignora en SQLite, por lo que no hay bloqueo pesimista real.
Mitigaciones adoptadas:

1. Toda la aprobación corre en `transaction.atomic()`: el chequeo de estado, la
   revalidación de cruce y la escritura del nuevo estado ocurren en una sola unidad.
2. La revalidación se hace **después** de recargar la reserva y **antes** de escribir,
   de modo que el conflicto se evalúa contra el estado más reciente de la base.
3. Las pruebas cubren la secuencia completa de dos solicitudes en conflicto y la
   revalidación ante un conflicto creado después de la solicitud.
4. `select_for_update()` se mantiene en el código para que, al migrar a PostgreSQL
   como prevé el plan 3.3, el bloqueo de filas funcione sin cambios de lógica.

- **Riesgo residual**: entre la lectura y la escritura, dos transacciones concurrentes
  en SQLite podrían pasar la validación antes de que alguna escriba. La ventana es
  pequeña, el sistema es de un solo proceso académico y el plan ya documenta R8. La
  solución definitiva es PostgreSQL con bloqueo de filas o un mecanismo de bloqueo a
  nivel de aplicación; ambos quedan fuera de alcance.
- **Alternativa descartada**: restricción `EXCLUDE` en base de datos. SQLite no la
  soporta y expresar solapamiento requeriría rangos, lo que obligaría a cambiar
  `fecha` + horas por un rango, decisión que pertenece al modelo de `solicitud-reserva`.
- **Alternativa descartada**: bloqueo global en memoria. No funciona con múltiples
  procesos y añade estado compartido innecesario.

### 5. Servicio de franjas ocupadas

```text
franjas_ocupadas(*, espacio, fecha)
```

Devuelve un queryset de reservas `APROBADA` para el espacio y fecha, ordenado por
`hora_inicio`, con `hora_inicio` y `hora_fin` (y opcionalmente el `pk`) suficientes
para la vista. No expone solicitante ni motivo. La consulta se ejecuta en cada
petición, sin caché ni dato denormalizado, de modo que refleja el estado vigente de
las reservas.

- **Motivo**: REQ-DIS-008 pide mostrar solo franjas ocupadas por aprobadas; limitar
  los campos evita filtrar datos personales de quien reservó. Calcular en cada
  petición evita resultados obsoletos tras una aprobación o una cancelación.
- **Alcance**: solo franjas ocupadas. El cálculo de franjas libres, sugerencias de
  horario y disponibilidad agregada quedan explícitamente fuera de alcance.
- **Alternativa descartada**: calcular franjas libres. El requisito pide disponibilidad
  mostrando ocupación; generar una parrilla de libres añade lógica no solicitada.
- **Alternativa descartada**: cachear o persistir un resumen de ocupación. Introduce
  invalidación y puede mostrar franjas que ya no están aprobadas.
- **Alternativa descartada**: reutilizar `validar_disponibilidad` para consultar. Esa
  función lanza excepción y no devuelve un listado; mezclar consulta y validación
  complica la vista.

### 6. Vista y plantilla de disponibilidad

`DisponibilidadView(LoginRequiredMixin, TemplateView)` en
`reservations/views.py`, ruta `reservas/disponibilidad/` con nombre
`reservations:disponibilidad`.

- Parámetros GET: `espacio` (id) y `fecha` (ISO `YYYY-MM-DD`).
- Formulario `DisponibilidadForm(forms.Form)` con `ModelChoiceField` limitado a
  espacios activos y `DateField` con valor inicial `timezone.localdate()`.
- Sin parámetros: se muestra el formulario sin resultados.
- Parámetros válidos: se muestran las franjas de `franjas_ocupadas` y un mensaje de
  "sin franjas ocupadas" cuando el queryset está vacío.
- Parámetros inválidos: se muestran errores del formulario y ninguna franja.
- Acceso: cualquier usuario autenticado; anónimo redirige al login.

Plantilla `reservations/templates/reservations/disponibilidad.html`, con selector de
espacio, fecha, tabla de franjas y enlaces de regreso al listado de reservas. Se
agregan enlaces desde `solicitud_lista.html` y desde la barra de navegación de
`templates/base.html`.

- **Motivo**: formulario GET simple, verificable con el cliente de pruebas y sin
  estado en servidor.
- **Alternativa descartada**: endpoint JSON con JavaScript. Fuera del estilo del
  proyecto y no aporta al requisito.
- **Alternativa descartada**: permitir consultar espacios inactivos. El requisito de
  `espacios` solo los muestra al administrador y no tendría sentido reservarlos.

### 7. Sin cambios de esquema

No se agregan modelos, campos ni migraciones. `validar_disponibilidad` usa la
restricción existente de `Reserva` y los estados de `solicitud-reserva`.

- **Motivo**: la información necesaria ya existe y una migración vacía solo añadiría
  ruido al historial.
- **Rendimiento**: no hay índice por `(espacio, fecha, estado)`. Con el volumen
  académico previsto es aceptable; si crece, se agrega en un cambio con migración y
  medición.

### 8. Pruebas

`reservations/tests/test_disponibilidad.py` y ampliaciones a los archivos existentes:

- **Servicio de cruces**: tabla de casos con reserva aprobada de 10:00–12:00 frente a
  09:00–13:00, 10:00–12:00, 09:00–11:00, 11:00–13:00, 10:30–11:30, 09:00–10:00
  (contiguo), 12:00–13:00 (contiguo), 10:59–12:00 (un minuto) y 10:00–10:01.
- **Estados**: pendiente, rechazada y cancelada no bloquean; aprobada bloquea.
- **Dimensiones**: mismo horario en otro espacio y en otra fecha se acepta.
- **Creación**: integración con `crear_solicitud` y mensaje con espacio, fecha y
  franja; el formulario muestra el error en el campo de hora.
- **Aprobación**: conflicto con aprobada, conflicto creado después de la solicitud,
  dos pendientes que se cruzan, aprobación válida, estado no pendiente y actor sin rol.
- **Disponibilidad**: solo aprobadas, orden por hora, fecha vacía, parámetros
  inválidos, espacio inactivo, anónimo redirigido y recálculo tras aprobar una nueva
  reserva entre dos consultas.
- **Límites horarios**: contigüidad en ambos sentidos, un minuto de solapamiento y
  franjas que usan los extremos del horario operativo (06:00 y 22:00) con una reserva
  aprobada.

Los casos usan fechas futuras relativas y `ahora` inyectado donde el servicio lo
permite, para no depender de la hora de ejecución.

- **Motivo**: el plan 5.3 exige una prueba por escenario; la matriz evita que un cruce
  parcial quede sin cubrir.
- **Pruebas de concurrencia real**: no se escriben con hilos porque SQLite las hace
  no deterministas; se prueba la secuencia equivalente de revalidación y se documenta
  la limitación.

## Risks / Trade-offs

- **Ventana de carrera en SQLite** → mitigación con transacción atómica, recarga y
  revalidación; riesgo residual documentado. Migrar a PostgreSQL habilita
  `select_for_update` real.
- **Aprobación mínima sin interfaz** → `aprobar_reserva` existe pero no se puede
  invocar desde la web todavía. Es intencional: la UI y la historia de estados llegan
  en `aprobacion`; mientras tanto se prueba por servicio.
- **Duplicidad futura de la aprobación** → el cambio `aprobacion` debe reutilizar
  `aprobar_reserva` y no reimplementar el chequeo; se anota como dependencia.
- **Mensaje de conflicto expone la franja ocupada** → es información necesaria para
  que el usuario elija otro horario y no revela identidad ni motivo.
- **Disponibilidad sin franjas libres** → el requisito solo pide ocupación; una
  parrilla de libres puede agregarse después sin cambiar requisitos.
- **Sin índice por espacio/fecha** → aceptable para el volumen previsto; se anota la
  optimización futura.
- **Solicitudes pendientes sin bloquear** → pueden acumularse varias para la misma
  franja; la aprobación resolverá el conflicto y las demás quedarán pendientes o se
  rechazarán en la capacidad correspondiente.

## Migration Plan

1. Confirmar que `solicitud-reserva` está implementado y con su suite en verde.
2. Implementar `validar_disponibilidad` y `franjas_ocupadas` en
   `reservations/services.py`.
3. Integrar la validación en `crear_solicitud` y agregar `aprobar_reserva` con
   transacción y revalidación.
4. Agregar `DisponibilidadForm`, la vista y la ruta; actualizar la navegación y el
   listado de reservas.
5. Crear la plantilla de disponibilidad.
6. Escribir las pruebas y ejecutar `python manage.py test` completa.

**Rollback**: revertir el commit. No hay migraciones ni datos nuevos que deshacer; las
reservas aprobadas durante las pruebas se eliminan con la base de desarrollo.

## Open Questions

Ninguna que afecte las especificaciones, el enfoque o el desglose de tareas. La
decisión sobre si las solicitudes `PENDIENTE` bloquean ya está resuelta por el plan
2.6 (solo `APROBADA` bloquea) y por REQ-DIS-002.
