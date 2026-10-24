# Spec Delta

## Purpose

Permite cancelar reservas propias o cualquier reserva cuando el actor es
administrador, respetando el estado y la hora de inicio, libera el espacio de una
reserva aprobada y conserva un historial inmutable de cada transición, consultable
con alcance por usuario y filtros.

## ADDED Requirements

### Requirement: REQ-CAN-001 Cancelación por el solicitante

Un usuario autenticado SHALL poder cancelar una reserva de la que sea solicitante
cuando esté en estado `PENDIENTE` o `APROBADA` y su hora de inicio no haya comenzado.
La cancelación SHALL fijar el estado `CANCELADA`, conservar los demás datos de la
reserva —incluida `fecha_decision` cuando la reserva fue aprobada o rechazada— y
registrar el evento de historial en la misma transacción.

#### Scenario: El solicitante cancela una reserva pendiente

- **GIVEN** un usuario autenticado con una reserva propia en estado `PENDIENTE` cuya hora de inicio es futura
- **WHEN** confirma la cancelación mediante una petición POST
- **THEN** la reserva pasa a estado `CANCELADA`
- **AND** la respuesta redirige al detalle de la reserva con un mensaje de confirmación
- **AND** se crea un evento de historial con estado anterior `PENDIENTE`, estado nuevo `CANCELADA` y el solicitante como actor

#### Scenario: El solicitante cancela una reserva aprobada

- **GIVEN** un usuario autenticado con una reserva propia en estado `APROBADA` cuya hora de inicio es futura
- **WHEN** cancela la reserva
- **THEN** la reserva pasa a estado `CANCELADA`
- **AND** se crea un evento de historial con estado anterior `APROBADA`, estado nuevo `CANCELADA` y el solicitante como actor

#### Scenario: Un aprobador cancela su propia reserva

- **GIVEN** un usuario con rol `APROBADOR` que es solicitante de una reserva `PENDIENTE` futura
- **WHEN** cancela su propia reserva
- **THEN** la cancelación se acepta aunque el usuario no sea administrador
- **AND** el actor del historial es ese mismo usuario

#### Scenario: La cancelación conserva los datos originales de la reserva

- **GIVEN** una reserva propia con espacio, fecha, franja, motivo y solicitante conocidos
- **WHEN** se cancela correctamente
- **THEN** el espacio, la fecha, las horas, el motivo y el solicitante no cambian
- **AND** solo cambian el estado y la fecha de actualización

#### Scenario: La cancelación conserva la fecha de decisión

- **GIVEN** una reserva `APROBADA` con `fecha_decision` registrada en el momento de la aprobación
- **WHEN** el solicitante cancela la reserva
- **THEN** `fecha_decision` conserva el valor original
- **AND** solo cambian el estado y `actualizado_en`
- **AND** el historial registra la transición `APROBADA → CANCELADA`

#### Scenario: El detalle solo ofrece cancelar cuando la reserva es cancelable

- **GIVEN** un solicitante con una reserva propia cancelable y otra ya iniciada
- **WHEN** abre el detalle de cada una
- **THEN** solo la reserva cancelable muestra la acción de cancelar
- **AND** la reserva ya iniciada muestra el motivo por el que no puede cancelarse

### Requirement: REQ-CAN-002 Cancelación por el administrador

Un usuario con rol `ADMINISTRADOR` SHALL poder cancelar cualquier reserva en estado
`PENDIENTE` o `APROBADA`, antes de su hora de inicio, sin importar quién sea el
solicitante. La cancelación SHALL registrar al administrador como actor del evento.

#### Scenario: El administrador cancela una reserva ajena pendiente

- **GIVEN** una reserva `PENDIENTE` futura cuyo solicitante es otro usuario
- **AND** un usuario con rol `ADMINISTRADOR`
- **WHEN** el administrador confirma la cancelación
- **THEN** la reserva pasa a estado `CANCELADA`
- **AND** el historial registra al administrador como actor
- **AND** el solicitante original no cambia

#### Scenario: El administrador cancela una reserva ajena aprobada

- **GIVEN** una reserva `APROBADA` futura de otro usuario
- **AND** un usuario con rol `ADMINISTRADOR`
- **WHEN** cancela la reserva
- **THEN** la reserva pasa a estado `CANCELADA`
- **AND** el espacio queda disponible para esa franja
- **AND** el historial registra la transición `APROBADA → CANCELADA` con el administrador como actor

#### Scenario: El administrador cancela su propia reserva

- **GIVEN** un usuario con rol `ADMINISTRADOR` que es solicitante de una reserva `PENDIENTE` futura
- **WHEN** cancela su propia reserva
- **THEN** la cancelación se acepta
- **AND** el historial registra al administrador como actor y solicitante

#### Scenario: El detalle de una reserva ajena ofrece cancelar al administrador

- **GIVEN** una reserva `PENDIENTE` futura de otro usuario
- **AND** un usuario con rol `ADMINISTRADOR`
- **WHEN** abre el detalle de esa reserva
- **THEN** la respuesta tiene estado 200
- **AND** se muestra la acción de cancelar

### Requirement: REQ-CAN-003 Estados no cancelables

Una reserva en estado `RECHAZADA` o `CANCELADA` SHALL NOT poder cancelarse, ni por
su solicitante ni por un `ADMINISTRADOR`. El intento SHALL rechazarse sin modificar
la reserva, sin liberar el espacio y sin crear un registro de historial.

#### Scenario: Cancelar una reserva rechazada falla

- **GIVEN** una reserva propia en estado `RECHAZADA`
- **WHEN** el solicitante intenta cancelarla
- **THEN** la operación se rechaza con un error que indica que el estado no permite cancelar
- **AND** la reserva conserva el estado `RECHAZADA`
- **AND** no se crea ningún registro de historial

#### Scenario: Cancelar una reserva ya cancelada falla

- **GIVEN** una reserva propia en estado `CANCELADA`
- **WHEN** el solicitante intenta cancelarla de nuevo
- **THEN** la operación se rechaza con un error de estado
- **AND** no se crea un segundo evento de cancelación

#### Scenario: El administrador tampoco cancela una reserva rechazada o cancelada

- **GIVEN** una reserva en estado `RECHAZADA` y otra en estado `CANCELADA`
- **AND** un usuario con rol `ADMINISTRADOR`
- **WHEN** intenta cancelar cualquiera de las dos
- **THEN** ambas operaciones se rechazan
- **AND** los estados y el historial existente no cambian

#### Scenario: La vista informa el estado no cancelable sin cambiar la reserva

- **GIVEN** una reserva propia en estado `RECHAZADA` o `CANCELADA`
- **WHEN** el solicitante envía la petición de cancelación
- **THEN** la respuesta tiene estado 200 con un mensaje de error
- **AND** la reserva conserva su estado
- **AND** la acción de cancelar no se ofrece en el detalle

### Requirement: REQ-CAN-004 Reservas ya iniciadas

Una reserva SHALL NOT poder cancelarse cuando su fecha y hora de inicio, combinadas
en la zona horaria local, sean anteriores o iguales al instante de la operación.
Solo se admite la cancelación estrictamente anterior al inicio; el límite exacto
cuenta como reserva ya iniciada.

#### Scenario: La cancelación un minuto antes del inicio se acepta

- **GIVEN** una reserva propia cuya fecha y hora de inicio es un minuto posterior al instante de la operación
- **WHEN** el solicitante la cancela
- **THEN** la reserva pasa a estado `CANCELADA`
- **AND** se registra el evento de historial

#### Scenario: La cancelación en el instante exacto del inicio falla

- **GIVEN** una reserva propia cuya fecha y hora de inicio es exactamente igual al instante de la operación
- **WHEN** el solicitante intenta cancelarla
- **THEN** la operación se rechaza con un error que indica que la reserva ya inició
- **AND** la reserva conserva su estado
- **AND** no se crea historial

#### Scenario: La cancelación después del inicio falla

- **GIVEN** una reserva propia cuya fecha y hora de inicio ya pasó
- **WHEN** el solicitante intenta cancelarla
- **THEN** la operación se rechaza
- **AND** la reserva conserva su estado y no se crea historial

#### Scenario: La cancelación de una reserva de una fecha pasada falla

- **GIVEN** una reserva propia cuya fecha es anterior a la fecha actual
- **WHEN** el solicitante intenta cancelarla
- **THEN** la operación se rechaza por reserva ya iniciada
- **AND** el estado no cambia

#### Scenario: La vista informa la reserva iniciada sin cambiar el estado

- **GIVEN** una reserva propia ya iniciada
- **WHEN** el solicitante envía la petición de cancelación
- **THEN** la respuesta tiene estado 200 con un mensaje de error
- **AND** la reserva conserva su estado
- **AND** el detalle no ofrece la acción de cancelar

### Requirement: REQ-CAN-005 Liberación del espacio

Al cancelar una reserva `APROBADA`, su franja SHALL dejar de considerarse ocupada.
La reserva cancelada SHALL NOT bloquear la disponibilidad ni impedir que otra
solicitud del mismo espacio, fecha y franja se apruebe. Este requisito es el lugar
donde se verifica que una segunda solicitud pueda aprobarse tras liberarse la primera;
`disponibilidad` no define esa transición y remite aquí.

#### Scenario: El horario queda libre al cancelar una reserva aprobada

- **GIVEN** una reserva `APROBADA` para un espacio, fecha y franja determinados
- **WHEN** la reserva se cancela
- **THEN** la validación de disponibilidad para ese espacio, fecha y franja no reporta conflicto
- **AND** la reserva cancelada no aparece entre las franjas ocupadas

#### Scenario: Otra solicitud del mismo horario puede aprobarse tras la cancelación

- **GIVEN** una reserva `APROBADA` que ocupa una franja
- **AND** una segunda solicitud `PENDIENTE` para la misma franja que no puede aprobarse mientras la primera esté aprobada
- **WHEN** la primera reserva se cancela y luego se aprueba la segunda
- **THEN** la segunda solicitud pasa a estado `APROBADA`
- **AND** la validación de disponibilidad no encuentra conflicto con la reserva cancelada

#### Scenario: La cancelación de una reserva pendiente no altera la disponibilidad

- **GIVEN** una reserva `PENDIENTE` que no bloquea la franja
- **WHEN** se cancela
- **THEN** la disponibilidad de la franja sigue siendo la misma
- **AND** la reserva pasa a `CANCELADA` con su evento de historial

### Requirement: REQ-CAN-006 Prohibición de cancelar reservas ajenas

Un usuario autenticado SHALL NOT poder cancelar una reserva de otro usuario, salvo
que tenga rol `ADMINISTRADOR`. El rol `APROBADOR` SHALL NOT otorgar permiso de
cancelación sobre reservas ajenas. La vista SHALL responder 403 y el servicio SHALL
rechazar la operación sin cambios.

#### Scenario: Otro solicitante recibe 403 al intentar cancelar una reserva ajena

- **GIVEN** una reserva `PENDIENTE` futura de otro usuario
- **AND** un usuario autenticado con rol `SOLICITANTE` que no es el dueño
- **WHEN** intenta cancelar la reserva
- **THEN** la respuesta tiene estado 403
- **AND** la reserva conserva su estado
- **AND** no se crea historial

#### Scenario: Un aprobador recibe 403 sobre una reserva ajena

- **GIVEN** una reserva `PENDIENTE` futura de otro usuario
- **AND** un usuario con rol `APROBADOR` que no es el solicitante
- **WHEN** intenta cancelar la reserva
- **THEN** la respuesta tiene estado 403
- **AND** la reserva no cambia

#### Scenario: El servicio rechaza la cancelación ajena aunque se invoque directamente

- **GIVEN** una reserva de otro usuario y un actor autenticado sin rol `ADMINISTRADOR`
- **WHEN** se invoca el servicio de cancelación directamente
- **THEN** la operación se rechaza con un error de permisos
- **AND** la reserva conserva su estado y no se crea historial

#### Scenario: Un visitante anónimo es redirigido al login

- **GIVEN** un visitante no autenticado
- **WHEN** solicita la ruta de cancelación de una reserva
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

#### Scenario: Una reserva inexistente responde 404

- **GIVEN** un usuario autenticado
- **WHEN** solicita cancelar un identificador de reserva que no existe
- **THEN** la respuesta tiene estado 404

### Requirement: REQ-HIS-001 Registro de cada transición

Cada cambio de estado de una reserva SHALL crear un registro en `HistorialReserva`
con reserva, estado anterior, estado nuevo, actor, fecha del evento y observación.
La creación SHALL registrarse con estado anterior nulo y estado nuevo `PENDIENTE`;
el rechazo SHALL conservar el motivo como observación.

#### Scenario: La creación de una solicitud registra su evento inicial

- **GIVEN** un usuario autenticado que crea una solicitud válida
- **WHEN** la solicitud se guarda
- **THEN** existe un registro de historial asociado a la reserva
- **AND** el estado anterior es nulo y el estado nuevo es `PENDIENTE`
- **AND** el actor es el solicitante y la fecha del evento no es nula

#### Scenario: La aprobación registra su evento

- **GIVEN** una solicitud `PENDIENTE` y un aprobador autorizado
- **WHEN** la solicitud se aprueba
- **THEN** se crea un registro con estado anterior `PENDIENTE`, estado nuevo `APROBADA` y el aprobador como actor
- **AND** la observación está vacía

#### Scenario: El rechazo registra su motivo como observación

- **GIVEN** una solicitud `PENDIENTE` y un aprobador autorizado
- **WHEN** la solicitud se rechaza con un motivo
- **THEN** se crea un registro con estado anterior `PENDIENTE`, estado nuevo `RECHAZADA` y el aprobador como actor
- **AND** la observación contiene el motivo del rechazo

#### Scenario: La cancelación registra su evento

- **GIVEN** una reserva `PENDIENTE` o `APROBADA` que se cancela correctamente
- **WHEN** la cancelación termina
- **THEN** se crea un registro con el estado anterior correspondiente, estado nuevo `CANCELADA` y el actor de la operación
- **AND** la fecha del evento corresponde al momento de la cancelación

#### Scenario: Una transición inválida no crea historial

- **GIVEN** una reserva en un estado que no permite la transición solicitada
- **WHEN** se intenta aprobar, rechazar o cancelar
- **THEN** la operación se rechaza
- **AND** no se agrega ningún registro de historial

### Requirement: REQ-HIS-002 Atomicidad del estado y el historial

La escritura del nuevo estado y la del registro de historial SHALL realizarse en una
misma transacción atómica. Si el historial no se puede guardar, el cambio de estado
SHALL revertirse y la reserva SHALL conservar su estado anterior.

#### Scenario: Un fallo al guardar el historial revierte la cancelación

- **GIVEN** una reserva cancelable
- **AND** un fallo simulado al crear el registro de historial
- **WHEN** se intenta cancelar la reserva
- **THEN** la operación falla
- **AND** la reserva conserva su estado anterior
- **AND** no queda ningún registro de historial nuevo

#### Scenario: Un fallo al guardar el historial revierte la creación

- **GIVEN** un usuario autenticado y datos de solicitud válidos
- **AND** un fallo simulado al crear el registro de historial
- **WHEN** se intenta crear la solicitud
- **THEN** la operación falla
- **AND** no queda ninguna reserva creada
- **AND** no queda ningún registro de historial

#### Scenario: Un fallo al guardar el historial revierte la aprobación

- **GIVEN** una solicitud `PENDIENTE` y un aprobador autorizado
- **AND** un fallo simulado al crear el registro de historial
- **WHEN** se intenta aprobar la solicitud
- **THEN** la operación falla
- **AND** la solicitud conserva el estado `PENDIENTE`
- **AND** no queda ningún registro de historial nuevo

### Requirement: REQ-HIS-003 Inmutabilidad del historial

Los registros de `HistorialReserva` SHALL ser inmutables desde la aplicación: no
SHALL poder modificarse ni eliminarse mediante el modelo, un queryset ni la
administración de Django. Solo SHALL permitirse insertar registros nuevos.

#### Scenario: Modificar un registro existente falla

- **GIVEN** un registro de historial existente
- **WHEN** se cambia uno de sus campos y se intenta guardar
- **THEN** la operación se rechaza
- **AND** el registro conserva sus valores originales en la base de datos

#### Scenario: Eliminar un registro individual falla

- **GIVEN** un registro de historial existente
- **WHEN** se intenta eliminar mediante su método de borrado
- **THEN** la operación se rechaza
- **AND** el registro sigue existiendo

#### Scenario: Eliminar registros de forma masiva falla

- **GIVEN** varios registros de historial
- **WHEN** se intenta eliminarlos mediante un queryset
- **THEN** la operación se rechaza
- **AND** todos los registros siguen existiendo

#### Scenario: La administración no permite modificar ni eliminar historial

- **GIVEN** el modelo de historial registrado en la administración de Django
- **WHEN** un administrador abre su listado o su detalle
- **THEN** no se ofrecen acciones de alta, edición ni borrado
- **AND** las comprobaciones de permiso de la administración rechazan esas acciones

#### Scenario: Insertar un registro nuevo sigue permitido

- **GIVEN** una reserva y un actor válidos
- **WHEN** se crea un registro de historial nuevo
- **THEN** la inserción se acepta
- **AND** el registro queda disponible para consulta

### Requirement: REQ-HIS-004 Visibilidad del historial

El solicitante SHALL poder consultar el historial de sus propias reservas. El
`ADMINISTRADOR` SHALL poder consultar el historial de todas las reservas. Un
`APROBADOR` que no sea el solicitante SHALL NOT ver el historial ajeno, aunque pueda
ver el detalle de la reserva. Un visitante anónimo SHALL ser redirigido al login.

#### Scenario: El solicitante solo ve el historial de sus reservas

- **GIVEN** un solicitante con reservas propias y reservas de otro usuario con historial
- **WHEN** abre el listado de historial
- **THEN** el listado incluye únicamente eventos de sus propias reservas
- **AND** no aparecen eventos de las reservas ajenas

#### Scenario: El administrador ve el historial de todas las reservas

- **GIVEN** reservas de varios solicitantes con eventos de historial
- **AND** un usuario con rol `ADMINISTRADOR`
- **WHEN** abre el listado de historial
- **THEN** el listado incluye eventos de todos los solicitantes
- **AND** cada evento muestra la reserva, la transición, el actor y la fecha

#### Scenario: El solicitante no amplía su alcance mediante filtros

- **GIVEN** un solicitante con historial propio y un espacio usado también por otro usuario
- **WHEN** filtra el historial por ese espacio
- **THEN** solo ve sus propios eventos para ese espacio
- **AND** no aparecen eventos del otro usuario

#### Scenario: El aprobador no ve el historial ajeno en el detalle

- **GIVEN** una reserva de otro usuario con historial
- **AND** un usuario con rol `APROBADOR` que no es el solicitante
- **WHEN** abre el detalle de la reserva
- **THEN** la respuesta tiene estado 200
- **AND** no se muestra la sección de historial
- **AND** el listado de historial solo contiene sus propios eventos

#### Scenario: El solicitante y el administrador ven el historial en el detalle

- **GIVEN** una reserva con eventos de historial
- **WHEN** el solicitante dueño o un administrador abre su detalle
- **THEN** se muestra la sección de historial con las transiciones ordenadas
- **AND** cada evento muestra estado anterior, estado nuevo, actor, fecha y observación

#### Scenario: Un visitante anónimo es redirigido al login desde el historial

- **GIVEN** un visitante no autenticado
- **WHEN** solicita el listado de historial
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

### Requirement: REQ-HIS-005 Filtros del historial

El listado de historial SHALL poder filtrarse por estado resultante, por fecha del
evento y por espacio de la reserva, de forma combinable. Los valores inválidos SHALL
ignorarse sin error y sin ampliar el alcance de visibilidad del usuario.

#### Scenario: El filtro por estado devuelve solo las transiciones correspondientes

- **GIVEN** eventos de historial con estados nuevos `PENDIENTE`, `APROBADA`, `RECHAZADA` y `CANCELADA`
- **WHEN** se filtra por estado `APROBADA`
- **THEN** el listado incluye únicamente eventos cuyo estado nuevo es `APROBADA`
- **AND** no aparecen eventos de otros estados

#### Scenario: El filtro por fecha devuelve los eventos de ese día

- **GIVEN** eventos de historial en fechas distintas
- **WHEN** se filtra por una fecha concreta
- **THEN** el listado incluye únicamente los eventos cuya fecha local coincide con esa fecha
- **AND** no aparecen eventos de otros días

#### Scenario: El filtro por espacio devuelve los eventos de ese espacio

- **GIVEN** eventos de historial de reservas en espacios distintos
- **WHEN** se filtra por un espacio
- **THEN** el listado incluye únicamente eventos de reservas de ese espacio

#### Scenario: Los filtros se combinan

- **GIVEN** eventos de varios estados, fechas y espacios
- **WHEN** se filtran simultáneamente por estado, fecha y espacio
- **THEN** el listado incluye solo los eventos que cumplen las tres condiciones
- **AND** el formulario conserva los valores seleccionados

#### Scenario: Los valores de filtro inválidos se ignoran

- **GIVEN** un listado de historial con eventos
- **WHEN** se envía un estado inexistente, una fecha mal formada o un espacio inexistente
- **THEN** la respuesta no produce un error
- **AND** el filtro inválido no se aplica
- **AND** el alcance de visibilidad del usuario se mantiene
