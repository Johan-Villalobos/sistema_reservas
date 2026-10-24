# Spec Delta

## Purpose

Permite a los usuarios autenticados solicitar un espacio académico en una fecha y
franja horaria determinadas, con validaciones de coherencia temporal, espacio
activo, motivo y horario operativo; registra cada solicitud en estado pendiente,
ofrece el listado de las solicitudes propias y expone el detalle solo a su
solicitante, a los aprobadores y a los administradores.

## ADDED Requirements

### Requirement: REQ-SOL-001 Creación de solicitudes por usuarios autenticados y activos

Todo usuario autenticado y activo SHALL poder crear una solicitud de reserva
indicando espacio, fecha, hora de inicio, hora de fin y motivo, sin importar su rol:
`SOLICITANTE`, `APROBADOR` o `ADMINISTRADOR`. El rol SHALL restringir la aprobación y
la administración, no la posibilidad de solicitar. El solicitante SHALL tomarse de la
sesión y no de los datos enviados por el cliente. Un visitante anónimo SHALL ser
redirigido al inicio de sesión.

#### Scenario: Un SOLICITANTE crea una solicitud válida que queda PENDIENTE

- **GIVEN** un usuario activo con rol `SOLICITANTE` y un espacio activo
- **WHEN** envía una solicitud con fecha futura, hora de inicio y fin válidas, dentro del horario operativo y con motivo
- **THEN** la solicitud se crea con estado `PENDIENTE`
- **AND** queda asociada al usuario autenticado como solicitante
- **AND** la respuesta redirige al detalle de la solicitud creada

#### Scenario: Un APROBADOR también puede crear una solicitud

- **GIVEN** un usuario activo con rol `APROBADOR` y un espacio activo
- **WHEN** envía una solicitud válida
- **THEN** la solicitud se crea con estado `PENDIENTE`
- **AND** queda asociada al aprobador como solicitante

#### Scenario: Un ADMINISTRADOR también puede crear una solicitud

- **GIVEN** un usuario activo con rol `ADMINISTRADOR` y un espacio activo
- **WHEN** envía una solicitud válida
- **THEN** la solicitud se crea con estado `PENDIENTE`
- **AND** queda asociada al administrador como solicitante

#### Scenario: El solicitante enviado por el cliente se ignora

- **GIVEN** un usuario autenticado distinto del solicitante que se intenta declarar
- **WHEN** envía una solicitud incluyendo el identificador de otro usuario como solicitante
- **THEN** la solicitud queda registrada a nombre del usuario autenticado
- **AND** el identificador enviado no tiene efecto

#### Scenario: Anónimo es redirigido al login

- **GIVEN** un visitante no autenticado
- **WHEN** solicita el formulario de creación de reservas
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

### Requirement: REQ-SOL-002 Estado inicial y datos de auditoría

Toda solicitud nueva SHALL quedar en estado `PENDIENTE` y SHALL registrar al
solicitante y la fecha y hora de creación. El cliente no SHALL poder crear
solicitudes en otro estado.

#### Scenario: La solicitud registra solicitante y fecha de creación

- **GIVEN** un usuario autenticado que crea una solicitud válida
- **WHEN** la solicitud se guarda
- **THEN** el campo de solicitante corresponde a ese usuario
- **AND** la fecha de creación queda registrada y no es nula

#### Scenario: Un estado enviado por el cliente se ignora

- **GIVEN** un usuario autenticado que manipula la solicitud e incluye `estado=APROBADA`
- **WHEN** la solicitud se procesa
- **THEN** la solicitud se crea con estado `PENDIENTE`
- **AND** no existe ninguna vía de creación que permita otro estado inicial

### Requirement: REQ-SOL-003 Franja horaria coherente y contenida en un día

La hora de fin SHALL ser mayor que la hora de inicio. La reserva SHALL estar
contenida en un mismo día: la fecha aplica tanto al inicio como al fin y el sistema
no SHALL aceptar franjas que crucen la medianoche.

#### Scenario: Hora de fin igual a la hora de inicio es rechazada

- **GIVEN** un usuario autenticado y un espacio activo
- **WHEN** envía una solicitud con hora de inicio y hora de fin iguales
- **THEN** la solicitud se rechaza con un error en el campo de hora de fin
- **AND** no se crea ninguna reserva

#### Scenario: Hora de fin menor que la hora de inicio es rechazada

- **GIVEN** un usuario autenticado y un espacio activo
- **WHEN** envía una solicitud con hora de fin anterior a la hora de inicio
- **THEN** la solicitud se rechaza con un error en el campo de hora de fin
- **AND** no se crea ninguna reserva

#### Scenario: La solicitud queda contenida en un solo día

- **GIVEN** un usuario autenticado que registra una solicitud con fecha, hora de inicio y hora de fin
- **WHEN** la solicitud se guarda
- **THEN** existe una única fecha asociada a la reserva
- **AND** el detalle muestra la misma fecha para el inicio y para el fin
- **AND** el formulario no ofrece un campo de fecha de fin

### Requirement: REQ-SOL-004 Rechazo de solicitudes en el pasado

El sistema SHALL rechazar las solicitudes cuya fecha y hora de inicio estén en el
pasado respecto de la hora local configurada. La comparación SHALL realizarse con la
fecha y la hora combinadas, no solo con la fecha.

#### Scenario: Fecha pasada es rechazada

- **GIVEN** un usuario autenticado y un espacio activo
- **WHEN** envía una solicitud con la fecha de ayer
- **THEN** la solicitud se rechaza con un error en la fecha o en la hora de inicio
- **AND** no se crea ninguna reserva

#### Scenario: Hora de inicio ya transcurrida en el día actual es rechazada

- **GIVEN** un usuario autenticado que envía una solicitud para hoy con una hora de inicio anterior a la hora actual
- **WHEN** la solicitud se procesa
- **THEN** se rechaza con un error de fecha u hora de inicio
- **AND** no se crea ninguna reserva

#### Scenario: Una solicitud futura es aceptada

- **GIVEN** un usuario autenticado y un espacio activo
- **WHEN** envía una solicitud para mañana en una franja válida
- **THEN** la solicitud se crea en estado `PENDIENTE`

### Requirement: REQ-SOL-005 Rechazo de solicitudes sobre espacios inactivos

El sistema SHALL rechazar las solicitudes cuyo espacio esté inactivo, incluso si el
identificador se envía manualmente y no figura en las opciones del formulario.

#### Scenario: Espacio inactivo es rechazado

- **GIVEN** un usuario autenticado y un espacio con estado inactivo
- **WHEN** envía una solicitud para ese espacio
- **THEN** la solicitud se rechaza con un error en el campo espacio
- **AND** no se crea ninguna reserva

#### Scenario: El formulario solo ofrece espacios activos

- **GIVEN** espacios activos e inactivos
- **WHEN** un usuario autenticado abre el formulario de creación
- **THEN** las opciones de espacio incluyen únicamente los activos
- **AND** los inactivos no aparecen en el selector

### Requirement: REQ-SOL-006 Motivo obligatorio con máximo 255 caracteres

Toda solicitud SHALL incluir un motivo no vacío de máximo 255 caracteres. Un motivo
vacío, compuesto solo por espacios o de más de 255 caracteres SHALL rechazarse sin
crear la reserva.

#### Scenario: Motivo vacío es rechazado

- **GIVEN** un usuario autenticado en el formulario de creación
- **WHEN** envía el motivo vacío o compuesto solo por espacios
- **THEN** la solicitud se rechaza con un error en el campo motivo
- **AND** no se crea ninguna reserva

#### Scenario: Motivo de 255 caracteres es aceptado

- **GIVEN** un usuario autenticado con una franja válida
- **WHEN** envía un motivo de exactamente 255 caracteres
- **THEN** la solicitud se crea correctamente

#### Scenario: Motivo mayor a 255 caracteres es rechazado

- **GIVEN** un usuario autenticado con una franja válida
- **WHEN** envía un motivo de 256 caracteres
- **THEN** la solicitud se rechaza con un error en el campo motivo
- **AND** no se crea ninguna reserva

### Requirement: REQ-SOL-007 Horario operativo configurable

Las solicitudes SHALL estar dentro del horario operativo definido como parámetro
configurable en `settings`, con valor inicial de 06:00 a 22:00. La hora de inicio
SHALL ser mayor o igual a la apertura y la hora de fin menor o igual al cierre.
Cambiar el parámetro SHALL cambiar el rango aceptado sin modificar el código.

#### Scenario: Hora fuera del horario operativo es rechazada

- **GIVEN** el horario operativo configurado de 06:00 a 22:00
- **WHEN** un usuario envía una solicitud que empieza antes de las 06:00 o termina después de las 22:00
- **THEN** la solicitud se rechaza con un error de horario
- **AND** no se crea ninguna reserva

#### Scenario: Los límites del horario operativo son aceptados

- **GIVEN** el horario operativo configurado de 06:00 a 22:00
- **WHEN** un usuario solicita una franja de 06:00 a 22:00 para una fecha futura
- **THEN** la solicitud se crea en estado `PENDIENTE`

#### Scenario: El horario operativo es configurable

- **GIVEN** una configuración que fija el horario operativo de 08:00 a 18:00
- **WHEN** un usuario solicita una franja de 07:00 a 09:00 o de 17:00 a 19:00
- **THEN** ambas solicitudes se rechazan
- **AND** una franja de 08:00 a 18:00 se acepta

### Requirement: REQ-SOL-008 Listado de solicitudes propias

Todo usuario autenticado SHALL poder listar sus propias solicitudes y ver el detalle
de cada una. El listado SHALL mostrar solo las solicitudes cuyo solicitante es el
usuario de la sesión. Un visitante anónimo SHALL ser redirigido al login.

#### Scenario: El usuario ve solo sus solicitudes

- **GIVEN** un usuario autenticado con solicitudes propias y solicitudes de otro usuario
- **WHEN** abre el listado de reservas
- **THEN** el listado incluye únicamente sus solicitudes
- **AND** no aparecen las solicitudes de otros usuarios

#### Scenario: El listado muestra el estado y la franja de cada solicitud

- **GIVEN** un usuario autenticado con al menos una solicitud
- **WHEN** abre el listado
- **THEN** cada fila muestra espacio, fecha, hora de inicio, hora de fin y estado
- **AND** ofrece el enlace al detalle de la solicitud

#### Scenario: Anónimo es redirigido al login desde el listado

- **GIVEN** un visitante no autenticado
- **WHEN** solicita el listado de reservas
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

### Requirement: REQ-SOL-009 Visibilidad restringida del detalle

El detalle de una solicitud SHALL ser visible solo para su solicitante, los usuarios
con rol `APROBADOR` y los usuarios con rol `ADMINISTRADOR`. Cualquier otro usuario
autenticado SHALL recibir una respuesta 403; un visitante anónimo SHALL ser
redirigido al login.

#### Scenario: El solicitante ve el detalle de su solicitud

- **GIVEN** una solicitud y el usuario que la creó
- **WHEN** el solicitante abre el detalle
- **THEN** la respuesta tiene estado 200
- **AND** se muestran espacio, fecha, franja, motivo y estado

#### Scenario: Un usuario no puede ver la solicitud de otro si no es aprobador o administrador

- **GIVEN** una solicitud creada por otro usuario
- **AND** un usuario autenticado con rol `SOLICITANTE` que no es el dueño
- **WHEN** solicita el detalle de esa solicitud
- **THEN** la respuesta tiene estado 403
- **AND** no se muestran los datos de la solicitud

#### Scenario: El APROBADOR puede ver el detalle de cualquier solicitud

- **GIVEN** una solicitud de otro usuario y un usuario con rol `APROBADOR`
- **WHEN** abre el detalle de la solicitud
- **THEN** la respuesta tiene estado 200

#### Scenario: El ADMINISTRADOR puede ver el detalle de cualquier solicitud

- **GIVEN** una solicitud de otro usuario y un usuario con rol `ADMINISTRADOR`
- **WHEN** abre el detalle de la solicitud
- **THEN** la respuesta tiene estado 200

### Requirement: REQ-SOL-010 Restricción de horas en la base de datos

La base de datos SHALL imponer que `hora_fin` sea mayor que `hora_inicio` mediante
una restricción `CHECK`, de modo que ninguna escritura inválida prospere aunque se
realice por fuera del formulario o del servicio.

#### Scenario: Una escritura directa con horas inválidas falla

- **GIVEN** una base de datos migrada
- **WHEN** se intenta insertar una reserva por ORM con hora de fin menor o igual a la hora de inicio
- **THEN** la operación falla con un error de integridad
- **AND** no queda ninguna fila insertada

#### Scenario: La migración crea la restricción

- **GIVEN** una base de datos vacía
- **WHEN** se ejecutan las migraciones de `reservations`
- **THEN** la tabla de reservas existe con una restricción `CHECK` que compara hora de fin y hora de inicio
- **AND** el intento de insertar horas inválidas se rechaza a nivel de base de datos

### Requirement: REQ-SOL-011 Cambios de estado solo a través de servicios

`Reserva.estado` SHALL modificarse únicamente mediante las funciones de servicio:
`crear_solicitud` para el estado inicial y `aprobar_reserva`, `rechazar_reserva` y
`cancelar_reserva` para las transiciones. Las vistas y los formularios SHALL NOT
asignar `estado`. SQLite no impide una escritura directa por ORM; esa vía se documenta
como no soportada y fuera del contrato.

#### Scenario: Una transición válida se ejecuta y registra en el servicio

- **GIVEN** una solicitud en estado `PENDIENTE`
- **WHEN** se aprueba mediante `aprobar_reserva`
- **THEN** el estado pasa a `APROBADA`
- **AND** el servicio registra el revisor y `fecha_decision`
- **AND** la vista de aprobación no asigna el estado por su cuenta

#### Scenario: La escritura directa de estado no está soportada

- **GIVEN** una solicitud en estado `PENDIENTE`
- **WHEN** se actualiza su `estado` con una escritura directa por ORM, sin invocar un servicio
- **THEN** SQLite permite la escritura porque no hay restricción de base que la impida
- **AND** el sistema no la considera una transición válida ni garantiza revisor, `fecha_decision` ni historial

El límite es inherente a SQLite y se documenta también en el informe de cierre. Una
restricción equivalente requeriría disparadores o un motor con más capacidades, ambos
fuera de alcance; la mitigación es concentrar las transiciones en servicios y
cubrirlas con pruebas.
