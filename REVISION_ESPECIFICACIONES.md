# Revisión de especificaciones

**Proyecto:** Sistema de Gestión de Reservas de Espacios Académicos  
**Documento revisado:** `PLAN_INGENIERIA.md` (secciones 1.2, 2.3–2.6, 3.3, 4.3 y 5.3)  
**Artefactos revisados:** todos los cambios de `openspec/changes/` (`base-proyecto`, `usuarios-roles-permisos`, `gestion-espacios`, `solicitud-reserva`, `disponibilidad-simultaneidad`, `aprobacion-rechazo`, `cancelacion-historial`)  
**Alcance:** revisión documental. No se modificó ningún archivo de `openspec/changes` ni se escribió código de la aplicación.  
**Fecha:** 24 de octubre de 2026

## Resumen ejecutivo

Se identificaron **65 hallazgos**: **8 de severidad alta**, **40 de severidad media** y **17 de severidad baja**.

Los riesgos principales son:

1. La secuencia `base-proyecto → usuarios-roles-permisos` obliga a reiniciar la base y regenerar la migración inicial de `accounts`, porque `base-proyecto` mantiene `auth.User` mientras `REQ-USR-001` exige el usuario personalizado desde la primera migración (H-01, H-44, H-52).
2. `REQ-BAS-007` confina todas las reglas de negocio a `reservations/services.py`, pero `accounts` y `spaces` también definen reglas propias (H-02, H-07, H-40).
3. La “fecha de decisión” de la aprobación se confunde con `actualizado_en`, que la cancelación posterior sobrescribe; se pierde la trazabilidad de N5 (H-05, H-58).
4. La necesidad N4 (“controlar quién puede solicitar”) no está realmente especificada: `REQ-SOL-001` permite solicitar a cualquier usuario autenticado (H-06, H-35).
5. La necesidad N2 (“disponibilidad en tiempo real”) queda cubierta solo por un listado de franjas ocupadas, sin definir disponibilidad libre ni “tiempo real” (H-14, H-36).
6. Varias reglas relevantes son invenciones respecto del plan y no están registradas como decisiones: protección del último administrador, prohibición de autodecisión, inmutabilidad del historial, horario operativo, filtros de historial y restricción temporal de cancelación (H-25 a H-32, H-54 a H-60).

La tabla de correspondencia N1–N8 está en la sección 7. Las decisiones que deben registrarse están en la sección 8.

---

## 1. Contradicciones entre especificaciones

### H-01 — `AUTH_USER_MODEL`: `base-proyecto` mantiene `auth.User`, `usuarios-roles` exige el usuario personalizado desde la primera migración

- **Severidad:** alta
- **Ubicación:** `openspec/changes/base-proyecto/design.md` (decisión 5, líneas 121–135); `openspec/changes/usuarios-roles-permisos/specs/usuarios-roles/spec.md` (`REQ-USR-001`); `openspec/changes/usuarios-roles-permisos/proposal.md` (Impact, líneas 60–63); `PLAN_INGENIERIA.md` 3.3.
- **Descripción:** El diseño de `base-proyecto` afirma explícitamente que no declara `AUTH_USER_MODEL` y que se mantiene `auth.User`. En cambio, `REQ-USR-001` exige un modelo personalizado “definido desde su primera migración” y que “ninguna tabla de usuario anterior quede en uso”. El plan 3.3 refuerza esa exigencia. La propuesta de `usuarios-roles` reconoce que hay que reiniciar `db.sqlite3` porque el proyecto base ya aplicó las tablas de `auth.User`. No es una simple secuencia: es una contradicción sobre el esquema inicial y sobre qué migración es la primera.
- **Corrección propuesta:** decidir una de dos vías y reflejarla en ambos cambios: (a) mover a `base-proyecto` la declaración de `AUTH_USER_MODEL` y un `Usuario` mínimo, dejando que `accounts` lo complete; o (b) declarar formalmente que `base-proyecto` es un andamiaje que no ejecuta `migrate` antes de `accounts`, y que `accounts` crea la primera migración real. En cualquiera de las dos, actualizar `base-proyecto/design.md`, sus tareas de verificación y `REQ-BAS-004`, y evitar que se publique una migración inicial de `auth.User` que luego haya que regenerar.

### H-02 — `REQ-BAS-007` exige todas las reglas en `reservations/services.py`, pero `accounts` y `spaces` definen reglas propias

- **Severidad:** alta
- **Ubicación:** `openspec/changes/base-proyecto/specs/base-proyecto/spec.md` (`REQ-BAS-007`, líneas 150–168); `openspec/changes/usuarios-roles-permisos/proposal.md` (Impact, línea 64: `accounts/services.py`); `openspec/changes/gestion-espacios/tasks.md` 1.4, 3.2 y 3.3 (normalización y validaciones en modelo/formulario); `PLAN_INGENIERIA.md` 2.1, 2.3 y 3.5.
- **Descripción:** `REQ-BAS-007` dice que “las reglas de negocio SHALL ubicarse en `reservations/services.py`” y su escenario exige que una regla nueva “resida en `reservations/services.py`”. Sin embargo, `accounts` planifica `accounts/services.py` para reglas como la protección del último administrador, y `spaces` implementa normalización de nombre, unicidad y validación de capacidad en `save()` y en formularios. La literalidad de `REQ-BAS-007` hace que esos diseños incumplan la especificación.
- **Corrección propuesta:** reformular `REQ-BAS-007` para que distinga la capa de servicios por aplicación: las reglas de disponibilidad, solapamiento y transiciones de reservas en `reservations/services.py`; las reglas de identidad en `accounts/services.py`; las de catálogo en `spaces/services.py` (o en el punto único que se decida). Añadir un escenario que verifique que cada módulo tiene su punto de entrada y que las vistas no contienen reglas.

### H-03 — `seed_data`: `base-proyecto` siembra `Group`, `usuarios-roles` lo reemplaza por usuarios y declara que no modifica capacidades

- **Severidad:** media
- **Ubicación:** `openspec/changes/base-proyecto/tasks.md` 5.2 y 5.3; `openspec/changes/base-proyecto/design.md` decisión 6 (líneas 142–159); `openspec/changes/usuarios-roles-permisos/tasks.md` 7.1–7.4; `openspec/changes/usuarios-roles-permisos/proposal.md` líneas 50–56.
- **Descripción:** Las tareas y el diseño de `base-proyecto` fijan que `seed_data` crea los grupos `Solicitante`, `Aprobador` y `Administrador`, y que `core/tests/test_seed_data.py` compara conteos de `Group`. `usuarios-roles` reemplaza esa siembra por usuarios de demostración y cambia las expectativas del test, pero su propuesta afirma “Modified Capabilities: Ninguna” y que `seed_data` “sigue siendo idempotente”. La idempotencia se conserva, pero el contrato observable y las pruebas del cambio base cambian.
- **Corrección propuesta:** declarar `base-proyecto` como capacidad modificada en `usuarios-roles` (o mover la prueba y la siembra de grupos al cambio de cuentas desde el inicio), y actualizar la especificación/tareas de `base-proyecto` para que `REQ-BAS-008` no fije `Group` como contrato. Si se mantiene el cambio de artefactos, registrar explícitamente la sustitución de grupos por usuarios.

### H-04 — `aprobar_solicitud` frente a `aprobar_reserva`: dos nombres y orden de tareas incompatible

- **Severidad:** media
- **Ubicación:** `openspec/changes/disponibilidad-simultaneidad/design.md` decisión 3 y `tasks.md` 2.3; `openspec/changes/aprobacion-rechazo/tasks.md` 2.2 y 2.4; `openspec/changes/cancelacion-historial/tasks.md` (precondición).
- **Descripción:** `disponibilidad-simultaneidad` implementa `aprobar_solicitud(*, reserva, actor)`. `aprobacion-rechazo` pide en la tarea 2.2 “implementar `aprobar_reserva`” y en la 2.4 “renombrar `aprobar_solicitud` a `aprobar_reserva`”. Si se ejecuta 2.2 primero, la 2.4 ya no tiene nada que renombrar y puede duplicar la función; si se ejecuta 2.4 primero, la 2.2 vuelve a crearla. Además, `cancelacion-historial` prescribe `_decidir_reserva` y no aclara cuál de los dos nombres sobrevive.
- **Corrección propuesta:** fijar un único nombre canónico desde `disponibilidad-simultaneidad` (por ejemplo `aprobar_reserva`) y eliminar el renombrado de `aprobacion-rechazo`, o convertir la tarea 2.4 en el primer paso y hacer que 2.2 construya sobre ella. Actualizar la precondición de `cancelacion-historial` y las pruebas de `disponibilidad`.

### H-05 — La “fecha de decisión” se confunde con `actualizado_en`, que la cancelación sobrescribe

- **Severidad:** alta
- **Ubicación:** `openspec/changes/aprobacion-rechazo/specs/aprobacion-rechazo/spec.md` (`REQ-APR-002`, líneas 61–62 y escenario línea 76); `openspec/changes/aprobacion-rechazo/design.md` líneas 72–78; `openspec/changes/cancelacion-historial/tasks.md` 4.2 y `design.md` decisión 2 (paso 7); `PLAN_INGENIERIA.md` 2.4.
- **Descripción:** `REQ-APR-002` exige “dejar constancia de la fecha de decisión”, pero el escenario habla de “la fecha de actualización de la solicitud” y el diseño usa `actualizado_en`. `cancelar_reserva` actualiza `actualizado_en` al cancelar, de modo que después de una cancelación la fecha de la aprobación o del rechazo deja de ser recuperable desde `Reserva`. `HistorialReserva` sí guarda `fecha_evento`, pero la especificación de aprobación no lo declara como fuente oficial. Esto afecta la trazabilidad de N5 y N6.
- **Corrección propuesta:** añadir `fecha_decision` a `Reserva` (nullable, solo para decisiones) o declarar en `REQ-APR-002` que la fecha oficial es el `fecha_evento` del evento de aprobación/rechazo en `HistorialReserva`. En ambos casos, cambiar el escenario para que no dependa de `actualizado_en` y añadir una prueba de que una cancelación posterior no borra la fecha de decisión.

---

## 2. Requisitos ambiguos o no verificables

### H-06 — `REQ-SOL-001` no define si cualquier rol puede solicitar o solo `SOLICITANTE`

- **Severidad:** media
- **Ubicación:** `openspec/changes/solicitud-reserva/specs/solicitud-reserva/spec.md` (`REQ-SOL-001`, líneas 13–18); `PLAN_INGENIERIA.md` 1.2 (N4), 1.3 y 2.2.
- **Descripción:** El requisito dice “Todo usuario autenticado SHALL poder crear una solicitud”. Eso incluye a `APROBADOR` y `ADMINISTRADOR`, aunque el plan describe al `Solicitante` como el actor que crea solicitudes y N4 exige “controlar quién puede solicitar, aprobar y administrar”. La especificación no aclara si se trata de una decisión deliberada o de un vacío. Tampoco hay un escenario con un aprobador o administrador creando una solicitud.
- **Corrección propuesta:** redactar explícitamente una de dos políticas: “solo el rol `SOLICITANTE` puede crear solicitudes” o “cualquier usuario autenticado puede crear solicitudes, incluidos `APROBADOR` y `ADMINISTRADOR`”. Añadir el escenario correspondiente para cada rol y registrar la decisión en la sección 8.

### H-07 — `REQ-BAS-007` no define “regla de negocio” y su escenario es una revisión de código, no una prueba de comportamiento

- **Severidad:** media
- **Ubicación:** `openspec/changes/base-proyecto/specs/base-proyecto/spec.md` (`REQ-BAS-007`, escenario líneas 163–168).
- **Descripción:** El escenario “Una nueva regla se implementa fuera de las vistas” pide revisar `reservations/views.py` y comprobar que “la regla reside en `reservations/services.py`”. No hay una regla concreta, un resultado observable ni un criterio objetivo: cualquier función auxiliar podría considerarse “regla” o no. Además, entra en conflicto con las reglas de `accounts` y `spaces` (H-02).
- **Corrección propuesta:** sustituir el escenario genérico por uno con una regla concreta (por ejemplo, “crear una solicitud con cruce horario devuelve error y no crea fila, y la vista solo invoca el servicio”). Definir “regla de negocio” como validación o transición que no dependa del formato de la petición y que tenga una prueba unitaria propia.

### H-08 — `REQ-ESP-002` exige rechazar cualquier tipo inválido, pero la especificación no dice en qué capa se garantiza

- **Severidad:** media
- **Ubicación:** `openspec/changes/gestion-espacios/specs/espacios/spec.md` (`REQ-ESP-002`, líneas 32–43); `openspec/changes/gestion-espacios/tasks.md` 1.1, 1.2, 3.4 y 2.3.
- **Descripción:** El requisito dice “Cualquier otro valor SHALL rechazarse sin crear ni modificar el espacio”, pero las tareas solo verifican el formulario (`is_valid()` falso) y usan `TextChoices`. `TextChoices` valida en formularios y en `full_clean()`, no en una escritura directa por ORM. Un `EspacioAcademico.objects.create(tipo="OTRO")` puede persistir un valor fuera del catálogo, incumpliendo la lectura absoluta del requisito.
- **Corrección propuesta:** añadir una `CheckConstraint` de base de datos para `tipo__in` (o restringir expresamente el requisito a “a través del formulario y de la validación del modelo”) y un escenario de escritura directa que falle. Si se elige la restricción, incluirla en la migración y en la prueba de restricciones.

### H-09 — `REQ-ESP-003` exige unicidad sin distinguir mayúsculas, pero no define la normalización de espacios internos

- **Severidad:** media
- **Ubicación:** `openspec/changes/gestion-espacios/specs/espacios/spec.md` (`REQ-ESP-003`, líneas 52–70); `openspec/changes/gestion-espacios/tasks.md` 1.4 y 3.2.
- **Descripción:** La especificación solo cubre mayúsculas/minúsculas. Las tareas añaden recorte de extremos y colapso de espacios internos (`"  Auditorio   Principal "` → `"Auditorio Principal"`), pero esa regla no aparece en el requisito ni en un escenario. Sin ella, `"Auditorio  Principal"` y `"Auditorio Principal"` podrían coexistir como nombres distintos, contradiciendo la intención de unicidad. Además, la normalización en `save()` no cubre `bulk_create`.
- **Corrección propuesta:** añadir a `REQ-ESP-003` la normalización obligatoria (trim y colapso de espacios internos) antes de comparar, y un escenario con dos nombres que solo difieren en espacios. Si se usa `UniqueConstraint(Lower("nombre"))`, documentar que la normalización debe ocurrir antes de guardar y probar también la edición.

### H-10 — `REQ-ESP-001` no define qué campos son obligatorios ni sus límites

- **Severidad:** media
- **Ubicación:** `openspec/changes/gestion-espacios/specs/espacios/spec.md` (`REQ-ESP-001`, líneas 12–30); `openspec/changes/gestion-espacios/tasks.md` 1.2 y 3.1.
- **Descripción:** El requisito enumera nombre, tipo, capacidad, ubicación, descripción y estado activo, pero no dice si nombre y ubicación son obligatorios, si descripción es opcional, ni los máximos. Las tareas fijan `nombre` máx. 120, `ubicacion` máx. 150 y `descripcion` opcional, pero eso no está en la especificación. Un espacio con nombre vacío o ubicación vacía no está cubierto por un escenario.
- **Corrección propuesta:** completar `REQ-ESP-001` con obligatoriedad y longitudes: nombre obligatorio (máx. 120), tipo obligatorio, capacidad obligatoria, ubicación obligatoria (máx. 150), descripción opcional y `activo` verdadero por defecto. Añadir escenarios para nombre/ubicación vacíos y para los límites.

### H-11 — `REQ-USR-006` no define los valores de rol admitidos ni el efecto “inmediato” en sesiones abiertas

- **Severidad:** media
- **Ubicación:** `openspec/changes/usuarios-roles-permisos/specs/usuarios-roles/spec.md` (`REQ-USR-006`, líneas 130–161).
- **Descripción:** El requisito permite “cambiar su rol” y que los cambios se reflejen “de inmediato en el acceso del usuario afectado”, pero no dice qué roles son válidos, qué ocurre con un rol inválido, si el administrador puede cambiar su propio rol, ni si un usuario ya autenticado pierde acceso en la siguiente petición o solo al volver a iniciar sesión. La protección del último administrador (`REQ-USR-007`) se cruza con este requisito y tampoco está coordinada en los escenarios.
- **Corrección propuesta:** enumerar los roles válidos (`SOLICITANTE`, `APROBADOR`, `ADMINISTRADOR`), rechazar cualquier otro, impedir la autodegradación cuando deje al sistema sin administrador y definir que el cambio de rol se evalúa en cada petición (no solo en el login). Añadir escenarios para rol inválido, cambio propio y cambio seguido de petición del usuario afectado.

### H-12 — `REQ-USR-002` no exige que el correo sea obligatorio ni define la unicidad en edición

- **Severidad:** media
- **Ubicación:** `openspec/changes/usuarios-roles-permisos/specs/usuarios-roles/spec.md` (`REQ-USR-002`, líneas 42–66); `openspec/changes/usuarios-roles-permisos/tasks.md` 1.2 y 1.3.
- **Descripción:** El requisito exige unicidad del correo sin distinguir mayúsculas y contraseña mínima, pero no dice que el correo sea obligatorio. Las tareas sí lo hacen obligatorio y añaden un manager que lo normaliza a minúsculas. Si el correo se deja vacío, la restricción de unicidad puede impedir más de una cuenta con cadena vacía, y el comportamiento no está especificado. Tampoco hay escenario de edición que intente duplicar el correo de otro usuario.
- **Corrección propuesta:** añadir “correo obligatorio, no vacío, normalizado a minúsculas antes de validar y único también en edición”, con escenarios para correo vacío, correo duplicado en edición y correo con mayúsculas. Alinear la longitud máxima con el modelo.

### H-13 — `REQ-SOL-007` no define el formato ni la validación del horario operativo configurable

- **Severidad:** media
- **Ubicación:** `openspec/changes/solicitud-reserva/specs/solicitud-reserva/spec.md` (`REQ-SOL-007`, líneas 161–186).
- **Descripción:** El requisito fija “parámetro configurable en `settings`” con valor inicial 06:00–22:00, pero no nombra las claves, no dice si son cadenas, `time` u horas enteras, ni qué ocurre si la apertura es posterior al cierre o si el valor es inválido. “Cambiar el parámetro SHALL cambiar el rango aceptado sin modificar el código” es verificable solo si se define el nombre exacto del ajuste.
- **Corrección propuesta:** fijar nombres y tipo (por ejemplo `HORARIO_APERTURA` y `HORARIO_CIERRE` como `datetime.time`), documentar la validación de `apertura < cierre` y añadir escenarios para configuración inválida y para el límite exacto de apertura/cierre.

### H-14 — `REQ-DIS-008` no define qué significa “disponibilidad” ni qué aporta “en tiempo real”

- **Severidad:** media
- **Ubicación:** `openspec/changes/disponibilidad-simultaneidad/specs/disponibilidad/spec.md` (`REQ-DIS-008`, líneas 175–201); `PLAN_INGENIERIA.md` 1.2 (N2) y 2.2.
- **Descripción:** El requisito pide “consultar la disponibilidad” pero el escenario solo lista franjas ocupadas por reservas aprobadas. No queda claro si “disponibilidad” significa “franjas libres”, “franjas ocupadas” o ambas, ni si “tiempo real” implica una consulta bajo demanda o una actualización automática. El diseño descarta explícitamente generar franjas libres. Un usuario no puede responder “¿está libre de 10:00 a 12:00?” sin inferirlo de las franjas ocupadas.
- **Corrección propuesta:** definir el resultado como “listado de franjas ocupadas por reservas aprobadas para espacio y fecha” y declarar fuera de alcance la parrilla de franjas libres, o añadir un requisito de franjas libres. Añadir un escenario que consulte una franja concreta y otro que muestre una fecha completamente libre.

### H-15 — `REQ-APR-003` no fija longitud máxima del motivo ni qué significa “normalizado”

- **Severidad:** baja
- **Ubicación:** `openspec/changes/aprobacion-rechazo/specs/aprobacion-rechazo/spec.md` (`REQ-APR-003`, líneas 99–142).
- **Descripción:** El motivo de rechazo es obligatorio y se normaliza, pero no se dice si tiene máximo, si se colapsan espacios internos o solo se recortan extremos. El modelo usa `TextField`, por lo que no hay límite. La ausencia de límite puede ser una decisión válida, pero no está declarada.
- **Corrección propuesta:** declarar explícitamente “sin límite máximo” o fijar uno (por ejemplo 500 caracteres) y precisar la normalización: `strip()` de extremos, conservando saltos de línea internos. Añadir un escenario de motivo con solo saltos de línea y otro con el máximo, si se define.

### H-16 — `REQ-HIS-005` no define cómo se informa un filtro inválido ni la zona horaria exacta

- **Severidad:** baja
- **Ubicación:** `openspec/changes/cancelacion-historial/specs/cancelacion-historial/spec.md` (`REQ-HIS-005`, líneas 416–455).
- **Descripción:** El requisito dice que los valores inválidos “se ignoran sin error”, pero no indica si el listado vuelve sin filtrar, si se conserva el valor en el formulario, ni si se muestra un aviso. Tampoco define si “fecha del evento” se interpreta en `America/Bogota` o en UTC; solo el escenario menciona “fecha local”.
- **Corrección propuesta:** precisar que un filtro inválido no se aplica, no produce error y no se conserva como selección válida; que la fecha se interpreta en la zona horaria activa (`America/Bogota`) y que el rango es el día local completo. Añadir un escenario con un evento cerca de la medianoche.

### H-17 — `REQ-BAS-005` usa “acceso a las secciones del usuario” sin definir enlaces ni rutas

- **Severidad:** baja
- **Ubicación:** `openspec/changes/base-proyecto/specs/base-proyecto/spec.md` (`REQ-BAS-005`, líneas 101–128); `openspec/changes/base-proyecto/design.md` líneas 208–211.
- **Descripción:** El escenario de usuario autenticado exige “el acceso a las secciones del usuario”, pero no enumera cuáles. El diseño reconoce que los enlaces apuntan a rutas aún inexistentes y que no se usan `{% url %}`. La verificación queda dependiente de una interpretación.
- **Corrección propuesta:** enumerar los enlaces exactos y su condición (por ejemplo “Mis reservas”, “Espacios”, “Cerrar sesión”), o sustituir “secciones del usuario” por “los enlaces definidos en el diseño” y añadir una tabla de rutas esperadas por cambio.

---

## 3. Requisitos sin escenario o con escenarios insuficientes

### H-18 — `REQ-DIS-003` tiene un solo escenario y no verifica que no se cree la reserva

- **Severidad:** media
- **Ubicación:** `openspec/changes/disponibilidad-simultaneidad/specs/disponibilidad/spec.md` (`REQ-DIS-003`, líneas 75–86).
- **Descripción:** El único escenario comprueba que la creación “informa el espacio, la fecha y la franja en conflicto”, pero no exige que no se cree ninguna fila ni que el error se asocie al campo de hora. La parte más importante de la regla —impedir la reserva— no está cubierta.
- **Corrección propuesta:** añadir “AND no se crea ninguna reserva” y “AND el error se asocia al campo `hora_inicio`”. Añadir un escenario de integración con `crear_solicitud` que cuente las reservas antes y después.

### H-19 — `REQ-DIS-009` tiene un solo escenario y no demuestra que creación y aprobación compartan la misma regla

- **Severidad:** media
- **Ubicación:** `openspec/changes/disponibilidad-simultaneidad/specs/disponibilidad/spec.md` (`REQ-DIS-009`, líneas 203–213).
- **Descripción:** El escenario “Creación y aprobación usan la misma regla” es genérico; no verifica que ambas rutas produzcan el mismo mensaje, que usen la misma función o que un cambio en una se refleje en la otra. Es fácil de cumplir con dos implementaciones duplicadas que casualmente coincidan.
- **Corrección propuesta:** añadir un escenario que compare el mensaje y el comportamiento de creación y aprobación ante el mismo cruce, y una prueba que verifique que ambas llaman a `validar_disponibilidad` (por ejemplo con un mock o con inspección de la función). Si se permite la duplicación, eliminar el requisito.

### H-20 — `REQ-USR-006` no cubre rol inválido, cambio propio ni efecto en una sesión ya abierta

- **Severidad:** media
- **Ubicación:** `openspec/changes/usuarios-roles-permisos/specs/usuarios-roles/spec.md` (`REQ-USR-006`, líneas 130–161).
- **Descripción:** Los escenarios cubren listar, cambiar a `APROBADOR`, desactivar y editar datos. No cubren un rol fuera del enum, el cambio del propio rol por parte del administrador, la coordinación con `REQ-USR-007` (último administrador) ni el efecto sobre un usuario que ya tiene sesión iniciada.
- **Corrección propuesta:** añadir escenarios para: rol inválido rechazado; cambio de rol propio bloqueado si deja sin administrador; usuario con sesión abierta al que se le cambia el rol y recibe 403 en la siguiente petición protegida; y cambio de rol permitido cuando hay otro administrador activo.

### H-21 — `REQ-ESP-001` no cubre campos vacíos, límites ni el carácter opcional de la descripción

- **Severidad:** media
- **Ubicación:** `openspec/changes/gestion-espacios/specs/espacios/spec.md` (`REQ-ESP-001`, líneas 12–30).
- **Descripción:** Solo hay dos escenarios: creación válida y conservación de ubicación/descripción al editar. No hay escenarios para nombre vacío, ubicación vacía, nombre de 121 caracteres, ubicación de 151, descripción vacía ni para comprobar que `activo` no se envía desde el formulario.
- **Corrección propuesta:** añadir los escenarios de campos obligatorios y límites, y uno que verifique que el formulario no permite fijar `activo` manualmente (si esa es la decisión).

### H-22 — `REQ-SOL-001` no cubre la creación por `APROBADOR` ni por `ADMINISTRADOR`

- **Severidad:** media
- **Ubicación:** `openspec/changes/solicitud-reserva/specs/solicitud-reserva/spec.md` (`REQ-SOL-001`, líneas 13–40).
- **Descripción:** Los escenarios cubren un usuario autenticado genérico, la suplantación de solicitante y el anónimo. No hay un escenario con un `APROBADOR` o un `ADMINISTRADOR` creando una solicitud, que es justamente el caso que la redacción amplia permite y que N4 podría querer restringir.
- **Corrección propuesta:** decidir la política de H-06 y añadir escenarios explícitos para cada rol. Si solo `SOLICITANTE` puede solicitar, añadir el 403 para los otros dos; si todos pueden, añadir la creación exitosa y la posterior prohibición de autodecisión.

### H-23 — `REQ-HIS-004` no cubre el historial propio de un aprobador ni el listado completo del administrador

- **Severidad:** media
- **Ubicación:** `openspec/changes/cancelacion-historial/specs/cancelacion-historial/spec.md` (`REQ-HIS-004`, líneas 364–414).
- **Descripción:** Los escenarios cubren al solicitante, al administrador y al aprobador que no ve historial ajeno, pero no cubren a un aprobador que sí es solicitante de algunas reservas y debe ver solo esas, ni el listado global del administrador con filtros. La regla “el aprobador no ve historial ajeno” queda bien cubierta; la parte “ve el propio” no.
- **Corrección propuesta:** añadir un escenario con un aprobador que tiene reservas propias y ajenas, y otro en el que el administrador combina filtros sobre el historial de todos. Verificar que el alcance por usuario se aplica antes de los filtros y que no se amplía con ellos.

### H-24 — `REQ-ESP-004` no verifica el rechazo de capacidad no entera en la base de datos

- **Severidad:** baja
- **Ubicación:** `openspec/changes/gestion-espacios/specs/espacios/spec.md` (`REQ-ESP-004`, líneas 72–89); `openspec/changes/gestion-espacios/tasks.md` 3.3.
- **Descripción:** El requisito dice que una capacidad no entera “SHALL rechazarse”, pero el escenario y la tarea solo prueban el formulario. La `CheckConstraint(Q(capacidad__gt=0))` no garantiza por sí sola que un valor textual se rechace en SQLite, y no hay un escenario de escritura directa por ORM.
- **Corrección propuesta:** añadir un escenario de inserción directa con capacidad `1.5` o `"texto"` que falle, o limitar el requisito a la validación de formulario/modelo y decirlo expresamente. Si se quiere garantía de base, usar un tipo adecuado y una restricción que cubra el caso.

---

## 4. Funcionalidades inventadas que no están en `PLAN_INGENIERIA.md`

> Estas funcionalidades pueden ser valiosas, pero no aparecen en el plan. No se propone eliminarlas automáticamente: se propone registrarlas como decisiones (sección 8) o justificar su exclusión.

### H-25 — Protección del último `ADMINISTRADOR` activo

- **Severidad:** alta
- **Ubicación:** `openspec/changes/usuarios-roles-permisos/specs/usuarios-roles/spec.md` (`REQ-USR-007`).
- **Descripción:** El plan solo dice que el administrador gestiona usuarios y roles; no exige la invariante “al menos un administrador activo”. Es una regla de negocio nueva, con impacto en desactivación y cambio de rol, y no está registrada como decisión.
- **Corrección propuesta:** registrar la invariante en la sección 8 y en el diseño, con su justificación. Si se rechaza, eliminar `REQ-USR-007` y sus escenarios; si se acepta, mantenerla y añadir el caso de dos administradores y el de auto-degradación.

### H-26 — Unicidad de correo sin distinguir mayúsculas y contraseña mínima de 8 caracteres

- **Severidad:** media
- **Ubicación:** `openspec/changes/usuarios-roles-permisos/specs/usuarios-roles/spec.md` (`REQ-USR-002`).
- **Descripción:** El plan 2.4 solo enumera el campo `email`; no fija unicidad, insensibilidad a mayúsculas ni política de contraseña. Son requisitos razonables, pero nuevos.
- **Corrección propuesta:** registrar ambas decisiones con su motivación y su alcance (registro, edición, `createsuperuser`). Aclarar si la contraseña mínima se aplica también a usuarios creados por `seed_data` y por el administrador.

### H-27 — Horario operativo configurable de 06:00 a 22:00

- **Severidad:** media
- **Ubicación:** `openspec/changes/solicitud-reserva/specs/solicitud-reserva/spec.md` (`REQ-SOL-007`).
- **Descripción:** El plan 1.5 solo limita las reservas a un mismo día; no menciona un horario operativo ni su configuración. Es una funcionalidad nueva que condiciona qué solicitudes se aceptan.
- **Corrección propuesta:** registrarla como decisión con las claves de configuración, el valor inicial y el procedimiento para cambiarlo. Si no se desea, eliminar `REQ-SOL-007` y sus escenarios y dejar solo la validación de mismo día.

### H-28 — Prohibición de autodecisión

- **Severidad:** media
- **Ubicación:** `openspec/changes/aprobacion-rechazo/specs/aprobacion-rechazo/spec.md` (`REQ-APR-005`); `openspec/changes/aprobacion-rechazo/design.md` decisión 4 (líneas 183–213).
- **Descripción:** El plan 2.5 solo exige que la aprobación o el rechazo los realice un `Aprobador` o `Administrador`; no prohíbe que decidan su propia solicitud. El diseño lo reconoce expresamente como “decisión nueva a confirmar”.
- **Corrección propuesta:** registrar la prohibición y su alcance (aprobación y rechazo, incluido el administrador). Si se rechaza, ajustar `REQ-APR-005`, los permisos y las pruebas; si se acepta, mantener la doble capa (permiso y servicio).

### H-29 — Inmutabilidad del historial desde la aplicación

- **Severidad:** media
- **Ubicación:** `openspec/changes/cancelacion-historial/specs/cancelacion-historial/spec.md` (`REQ-HIS-003`).
- **Descripción:** El plan 2.4 define `HistorialReserva` como registro de eventos, pero no exige que sea inmutable ni que se impida editar/eliminar. La inmutabilidad es una decisión de auditoría nueva.
- **Corrección propuesta:** registrarla con su alcance exacto: modelo, queryset, `bulk_update`, administración y límites (no cubre SQL crudo ni `bulk_create`). Si no se desea, reducir el requisito a “no se ofrece edición en la interfaz” y eliminar las pruebas de queryset.

### H-30 — Filtros del historial por estado, fecha y espacio

- **Severidad:** media
- **Ubicación:** `openspec/changes/cancelacion-historial/specs/cancelacion-historial/spec.md` (`REQ-HIS-005`).
- **Descripción:** El plan 1.3 solo dice que el administrador puede “consultar todo el historial” y el solicitante ver su historial; no menciona filtros. Los filtros son una funcionalidad adicional.
- **Corrección propuesta:** registrar los filtros como decisión y su comportamiento ante valores inválidos. Si el alcance debe ceñirse al plan, dejar solo el listado con alcance por usuario y mover los filtros a un cambio posterior.

### H-31 — Restricción de cancelación después de la hora de inicio

- **Severidad:** media
- **Ubicación:** `openspec/changes/cancelacion-historial/specs/cancelacion-historial/spec.md` (`REQ-CAN-004`).
- **Descripción:** El plan 2.5 define las transiciones `PENDIENTE → CANCELADA` y `APROBADA → CANCELADA`, pero no impone que la cancelación ocurra antes del inicio. La restricción temporal, incluido el límite exacto, es nueva.
- **Corrección propuesta:** registrarla con la regla exacta (`ahora < inicio` permite; `ahora >= inicio` bloquea) y la zona horaria. Si no se desea, permitir cancelar en cualquier momento y eliminar `REQ-CAN-004`.

### H-32 — Restricción de visibilidad del historial para el `APROBADOR`

- **Severidad:** media
- **Ubicación:** `openspec/changes/cancelacion-historial/specs/cancelacion-historial/spec.md` (`REQ-HIS-004`).
- **Descripción:** El plan 1.3 dice que el administrador consulta todo el historial y que el solicitante ve su historial; no dice que un aprobador no pueda ver el historial ajeno, aunque sí pueda ver el detalle de la reserva. La restricción es una decisión de privacidad nueva y crea una asimetría entre detalle e historial.
- **Corrección propuesta:** registrar la decisión y justificarla; si se acepta, mantener el escenario del aprobador que ve el detalle pero no la sección de historial. Si no, alinear con `REQ-SOL-009` y permitir al aprobador ver el historial de las reservas que puede ver.

### H-33 — Unicidad de nombre sin distinguir mayúsculas, capacidad positiva y descripción opcional

- **Severidad:** baja
- **Ubicación:** `openspec/changes/gestion-espacios/specs/espacios/spec.md` (`REQ-ESP-001`, `REQ-ESP-003`, `REQ-ESP-004`).
- **Descripción:** El plan 2.4 exige nombre único y capacidad, pero no precisa insensibilidad a mayúsculas, capacidad estrictamente positiva ni descripción opcional. Son refinamientos nuevos, no contradicciones.
- **Corrección propuesta:** registrarlos como decisiones de modelado. Si se aceptan, mantener las restricciones y las pruebas; si no, ajustar la especificación al plan.

### H-34 — Motivo obligatorio con máximo 255, evento de creación y rechazo de solicitudes pasadas

- **Severidad:** baja
- **Ubicación:** `openspec/changes/solicitud-reserva/specs/solicitud-reserva/spec.md` (`REQ-SOL-004`, `REQ-SOL-006`); `openspec/changes/cancelacion-historial/specs/cancelacion-historial/spec.md` (`REQ-HIS-001`).
- **Descripción:** El plan 2.4 enumera `motivo` y `creado_en`, pero no exige que el motivo sea obligatorio, que tenga máximo 255, que se rechacen solicitudes pasadas ni que la creación genere un evento de historial con `estado_anterior = NULL`. Son reglas nuevas que conviene registrar juntas como “reglas de validación y trazabilidad añadidas”.
- **Corrección propuesta:** registrarlas en la sección 8 con su motivación y sus escenarios. Si alguna no se desea, eliminarla del requisito correspondiente; por ejemplo, permitir motivo vacío o no generar evento de creación.

---

## 5. Elementos del plan que no están cubiertos por ninguna especificación

### H-35 — N4: “controlar quién puede solicitar” no está especificado

- **Severidad:** alta
- **Ubicación:** `PLAN_INGENIERIA.md` 1.2 (N4) y 1.3; `openspec/changes/solicitud-reserva/specs/solicitud-reserva/spec.md` (`REQ-SOL-001`).
- **Descripción:** N4 es una necesidad de prioridad alta: controlar quién puede solicitar, aprobar y administrar. Las especificaciones controlan aprobar (`REQ-APR-006`) y administrar (`REQ-USR-008`, `REQ-ESP-005`), pero no restringen quién puede solicitar: `REQ-SOL-001` permite a cualquier autenticado. No hay una decisión que justifique esa laxitud ni un requisito que la restrinja.
- **Corrección propuesta:** definir la política de solicitud (solo `SOLICITANTE` o todos los autenticados) y reflejarla en `REQ-SOL-001` con escenarios por rol. Si se mantiene “todos”, registrar la decisión y explicar cómo se cumple N4.

### H-36 — N2: “consultar disponibilidad en tiempo real” queda en un listado parcial de ocupación

- **Severidad:** alta
- **Ubicación:** `PLAN_INGENIERIA.md` 1.2 (N2) y 2.2; `openspec/changes/disponibilidad-simultaneidad/specs/disponibilidad/spec.md` (`REQ-DIS-008`).
- **Descripción:** N2 pide disponibilidad en tiempo real. La especificación ofrece un listado de franjas ocupadas por aprobadas, pero no calcula franjas libres, no define “tiempo real” y no incluye una vista de calendario. El plan 2.2 permite “calendario o listado”, pero el listado de ocupadas no responde directamente “¿está disponible esta franja?”.
- **Corrección propuesta:** ampliar `REQ-DIS-008` para que, dada una franja candidata, indique si está libre u ocupada, además de listar las ocupadas; o declarar explícitamente que la consulta es solo de ocupación y que la evaluación de una franja se hace al crear la solicitud. Añadir un escenario de consulta de una franja concreta.

### H-37 — El modelo `TipoEspacio` del plan 2.3 no está cubierto

- **Severidad:** media
- **Ubicación:** `PLAN_INGENIERIA.md` 2.3 (modelos `EspacioAcademico, TipoEspacio`); `openspec/changes/gestion-espacios/design.md` (sustitución por `TextChoices`); `REQ-ESP-002`.
- **Descripción:** El plan lista `TipoEspacio` como modelo principal de `spaces`. La especificación solo define un enum `TipoEspacio` y no crea tabla, clave foránea ni datos de tipos. La decisión está documentada en el diseño, pero no hay un requisito que la respalde ni una actualización del plan.
- **Corrección propuesta:** registrar formalmente la sustitución del modelo por `TextChoices` (sección 8) y actualizar la tabla del plan o la especificación. Si se necesita administrar tipos desde la base, crear el modelo y un requisito de CRUD; si no, dejar claro que los tipos son valores de código.

### H-38 — La carga inicial de roles, tipos, espacios y usuarios no tiene requisito de aceptación

- **Severidad:** media
- **Ubicación:** `PLAN_INGENIERIA.md` 3.3; `openspec/changes/base-proyecto/specs/base-proyecto/spec.md` (`REQ-BAS-008`); tareas 5.2 de `base-proyecto`, 7.1 de `usuarios-roles` y 6.1 de `gestion-espacios`.
- **Descripción:** El plan 3.3 exige cargar roles, tipos de espacio, espacios de ejemplo y usuarios de prueba mediante fixtures o `seed_data`. La especificación de `base-proyecto` solo dice “datos mínimos de demostración” y no enumera qué debe sembrarse; las tareas concretas viven en tres cambios distintos. No hay un escenario que verifique el conjunto completo ni que los tipos estén cubiertos (con `TextChoices` no hay datos que sembrar).
- **Corrección propuesta:** añadir a `REQ-BAS-008` el contrato de datos iniciales por etapa, o crear un requisito de “datos de demostración” con escenarios para roles/usuarios, espacios y tipos. Aclarar que los tipos, al ser `TextChoices`, no se siembran y que eso satisface el plan.

### H-39 — La invariante “el estado solo cambia mediante transiciones válidas” no tiene requisito global

- **Severidad:** media
- **Ubicación:** `PLAN_INGENIERIA.md` 2.4 (restricciones de integridad) y 2.5; `REQ-APR-004`, `REQ-CAN-003`.
- **Descripción:** El plan exige que el estado solo cambie mediante transiciones válidas. Las especificaciones cubren las transiciones de aprobación/rechazo y cancelación, pero no impiden que una vista, un formulario, el admin o una escritura directa cambien `Reserva.estado` a un valor arbitrario. No hay un requisito que prohíba `Reserva.objects.update(estado=...)` ni un escenario de escritura directa.
- **Corrección propuesta:** añadir un requisito de invariante de estado: toda transición pasa por un servicio autorizado y cualquier otro cambio se rechaza o se detecta; incluir un escenario de escritura directa/administración. Si no se puede garantizar en SQLite, documentar la limitación y al menos impedir las rutas de la aplicación.

### H-40 — N8: la separación de reglas en servicios solo cubre `reservations`

- **Severidad:** media
- **Ubicación:** `PLAN_INGENIERIA.md` 2.1, 3.5, 4.3 (dependencia transversal) y 1.2 (N8); `REQ-BAS-007`; `usuarios-roles` (`accounts/services.py`); `gestion-espacios` (validaciones en modelo/formulario).
- **Descripción:** N8 exige preparar el sistema para nuevas reglas de negocio, y el plan 3.5 justifica la capa de servicios porque “el cambio de la Fase 4 afecta un solo lugar”. Sin embargo, `REQ-BAS-007` solo nombra `reservations/services.py`, y las reglas de cuentas y espacios quedan en otros puntos. No hay una convención que garantice que una regla nueva de espacios o usuarios se pueda cambiar en un solo lugar.
- **Corrección propuesta:** definir una convención de servicios por aplicación y un requisito que exija que las reglas de cada módulo tengan un punto único. Añadir un escenario de cambio de regla en `spaces` o `accounts` que no toque vistas.

### H-41 — La matriz de trazabilidad del plan 5.3 no tiene artefacto ni tarea que la produzca

- **Severidad:** baja
- **Ubicación:** `PLAN_INGENIERIA.md` 5.3.
- **Descripción:** El plan exige una matriz requisito → archivo de código → pruebas. Las tareas de los cambios piden incluir el identificador en nombres/docstrings y “verificar la trazabilidad”, pero ninguna tarea crea la matriz ni define su formato o ubicación.
- **Corrección propuesta:** añadir una tarea de cierre que genere `MATRIZ_TRAZABILIDAD.md` (o una sección de `INFORME_FINAL.md`) con una fila por requisito, escenario, código y prueba. Verificarla en la revisión final.

### H-42 — La meta de cobertura del 80 % no está en ninguna tarea

- **Severidad:** baja
- **Ubicación:** `PLAN_INGENIERIA.md` 5.1.
- **Descripción:** El plan fija una meta mínima de 80 % en servicios y modelos y menciona `coverage.py`, pero ninguna tarea de los cambios ejecuta cobertura ni verifica el umbral. Las tareas solo ejecutan `manage.py test`.
- **Corrección propuesta:** añadir una tarea de cierre con `coverage run -m manage.py test` y `coverage report --fail-under=80`, o registrar que la meta se verifica solo en el informe final y no es un criterio de cada cambio.

### H-43 — El respaldo `dumpdata`/`loaddata` del plan 3.3 no tiene tarea

- **Severidad:** baja
- **Ubicación:** `PLAN_INGENIERIA.md` 3.3.
- **Descripción:** El plan describe el respaldo y la restauración como parte de la estrategia de persistencia, pero ningún cambio incluye una tarea o un escenario para probarlo. Es un elemento del plan sin cobertura.
- **Corrección propuesta:** añadir una tarea de cierre que ejecute `dumpdata`, restaure en una base limpia con `loaddata` y verifique los conteos; o declararlo explícitamente fuera de alcance y registrar la decisión.

---

## 6. Dependencias entre cambios y problemas de orden en las tareas

### H-44 — `base-proyecto` se implementa y migra antes de que `accounts` fije `AUTH_USER_MODEL`

- **Severidad:** alta
- **Ubicación:** `openspec/changes/base-proyecto/tasks.md` 6.4; `openspec/changes/usuarios-roles-permisos/tasks.md` 1.4 y 7.x; `openspec/changes/usuarios-roles-permisos/proposal.md` líneas 60–63; `PLAN_INGENIERIA.md` 3.3 y 4.3.
- **Descripción:** `base-proyecto` ordena migrar, sembrar y arrancar el servidor antes de `accounts`. `accounts` fija `AUTH_USER_MODEL` después y propone “reiniciar `db.sqlite3`” y regenerar la migración inicial. El plan 3.3 exige que el usuario personalizado se defina desde la primera migración y que las migraciones se versionen sin alterar las anteriores. La secuencia actual produce una migración inicial de `auth.User` que luego se descarta, y hace que la verificación de `base-proyecto` deje de ser reproducible después de `accounts`.
- **Corrección propuesta:** invertir el orden lógico: definir `AUTH_USER_MODEL` y la migración inicial de `accounts` antes de ejecutar la primera migración del proyecto, o convertir `base-proyecto` en un andamiaje sin `migrate` hasta que `accounts` exista. Actualizar la tarea 6.4 de `base-proyecto` y la precondición de `accounts`; no publicar una migración que luego se regenere.

### H-45 — La tarea de renombrado de `aprobar_solicitud` está después de la tarea que crea `aprobar_reserva`

- **Severidad:** media
- **Ubicación:** `openspec/changes/aprobacion-rechazo/tasks.md` 2.2 y 2.4; `openspec/changes/disponibilidad-simultaneidad/tasks.md` 2.3.
- **Descripción:** Es el mismo conflicto de H-04 visto como orden de ejecución. La tarea 2.2 ya implementa `aprobar_reserva`; la 2.4 intenta renombrar `aprobar_solicitud`, que ya no existe o que se duplicó. El orden no es ejecutable sin decidir cuál tarea se elimina.
- **Corrección propuesta:** mover el renombrado a la primera tarea del grupo 2 o eliminarlo; dejar una sola función canónica y actualizar las llamadas de `disponibilidad` en el mismo commit.

### H-46 — `REQ-DIS-007` exige un escenario que depende de la cancelación, que llega en un cambio posterior

- **Severidad:** media
- **Ubicación:** `openspec/changes/disponibilidad-simultaneidad/specs/disponibilidad/spec.md` (`REQ-DIS-007`, escenario líneas 169–173); `openspec/changes/cancelacion-historial/` (cambio posterior).
- **Descripción:** El escenario “Si la primera deja de estar aprobada, la segunda puede aprobarse” requiere una forma de sacar una reserva de `APROBADA`. En el alcance de `disponibilidad` no existe cancelación ni otra transición; solo se podría forzar con una escritura directa en la prueba, que no representa un flujo soportado. La prueba quedaría artificial o se pospondría.
- **Corrección propuesta:** mover ese escenario a `cancelacion-historial` (donde `REQ-CAN-005` ya cubre la liberación) o limitarlo a una prueba de servicio con cambio directo de estado, documentando que no es un flujo de usuario. Añadir la dependencia explícita en `disponibilidad`.

### H-47 — La vista de disponibilidad (plan 2.2, funcionalidad 7) se implementa en el cambio 4

- **Severidad:** media
- **Ubicación:** `PLAN_INGENIERIA.md` 2.2 (orden 7: consulta de disponibilidad) y 4.3; `openspec/changes/disponibilidad-simultaneidad/specs/disponibilidad/spec.md` (`REQ-DIS-008`) y `tasks.md` grupo 3.
- **Descripción:** El plan prioriza la consulta de disponibilidad después de aprobación y cancelación (orden 7), pero `disponibilidad-simultaneidad` la incluye junto con la validación de cruces (orden 4). No es un error funcional, pero altera el orden de incrementos y mezcla una mejora de usabilidad con la regla crítica de simultaneidad.
- **Corrección propuesta:** decidir si la vista se queda en el cambio 4 (y actualizar el orden del plan) o se mueve a un cambio posterior. Si se queda, separar las tareas de la vista de las de la regla para que la regla crítica pueda cerrarse antes.

### H-48 — Cambios que modifican artefactos de cambios anteriores sin declarar capacidad modificada

- **Severidad:** media
- **Ubicación:** `openspec/changes/usuarios-roles-permisos/proposal.md` (Modified Capabilities: Ninguna; Impact sobre `base.html` y `seed_data`); `openspec/changes/cancelacion-historial/proposal.md` (Modified Capabilities: Ninguna; Impact sobre `crear_solicitud` y `_decidir_reserva`).
- **Descripción:** `usuarios-roles` cambia la siembra y las pruebas de `base-proyecto`, y `cancelacion-historial` cambia el comportamiento de creación y decisión al escribir historial. Ambos declaran “Ninguna” capacidad modificada. Aunque los cambios previos no estén archivados, el contrato observable de sus capacidades cambia y la trazabilidad de OpenSpec queda incompleta.
- **Corrección propuesta:** declarar las capacidades modificadas (`base-proyecto` para `seed_data`/navegación; `solicitud-reserva` y `aprobacion-rechazo` para la escritura de historial) o mover esos cambios a los deltas correspondientes. Si se mantiene “Ninguna”, justificar por qué el comportamiento observable no cambia (lo cual no es el caso).

### H-49 — La verificación de arranque de `base-proyecto` no se repite tras `accounts` y `spaces`

- **Severidad:** baja
- **Ubicación:** `openspec/changes/base-proyecto/tasks.md` 6.4; `PLAN_INGENIERIA.md` 4.4 (no romper pruebas de etapas anteriores).
- **Descripción:** La tarea 6.4 borra la base, migra, siembra y arranca el servidor. Es una verificación válida para `base-proyecto`, pero después de `accounts` cambia `AUTH_USER_MODEL`, `seed_data` y la navegación; después de `spaces` cambia la siembra. Ningún cambio posterior repite esa verificación de arranque completo.
- **Corrección propuesta:** añadir al cierre de `accounts`, `spaces` y `reservations` una tarea de “base limpia: migrate + seed_data + runserver + suite completa”, o una tarea única de regresión al final.

### H-50 — `gestion-espacios` modifica el test de `seed_data` creado por `accounts`

- **Severidad:** baja
- **Ubicación:** `openspec/changes/gestion-espacios/tasks.md` 6.4; `openspec/changes/usuarios-roles-permisos/tasks.md` 7.3.
- **Descripción:** `gestion-espacios` amplía `core/tests/test_seed_data.py` para comprobar espacios y “conservando las comprobaciones de usuarios”. Ese archivo fue reescrito por `accounts`. La dependencia es correcta (accounts va antes), pero si `accounts` se archiva y luego se modifica su test, hay que declararlo como modificación cruzada.
- **Corrección propuesta:** mantener la dependencia explícita y añadir una nota en `gestion-espacios` de que el test base pertenece a `accounts`; o mover la prueba de espacios a `spaces/tests/` para no reescribir un artefacto ajeno.

### H-51 — La tarea 2.4 de `aprobacion-rechazo` actualiza pruebas de `disponibilidad` sin una tarea de regresión de ese cambio

- **Severidad:** baja
- **Ubicación:** `openspec/changes/aprobacion-rechazo/tasks.md` 2.4.
- **Descripción:** La tarea pide actualizar “todas las llamadas y pruebas de `disponibilidad`” al renombrar la función. Es una modificación de la suite de un cambio anterior; no hay una tarea separada que ejecute la suite completa de `disponibilidad` después del renombrado, aunque la propia tarea lo menciona.
- **Corrección propuesta:** hacer explícita la ejecución de `python manage.py test reservations.tests.test_disponibilidad` y de la suite completa después del renombrado, y registrar el cambio en la matriz de trazabilidad.

---

## 7. Tabla de correspondencia: necesidades N1–N8 del plan frente a requisitos

| Necesidad del plan | Requisitos que la cubren | Cobertura | Observaciones |
|---|---|---|---|
| **N1. Centralizar el catálogo de espacios y sus características** | `REQ-ESP-001`, `REQ-ESP-002`, `REQ-ESP-003`, `REQ-ESP-004`, `REQ-ESP-006`, `REQ-ESP-007`, `REQ-ESP-008` | Alta | Falta el modelo `TipoEspacio` del plan (H-37) y precisiones de campos (H-10). |
| **N2. Consultar disponibilidad en tiempo real** | `REQ-DIS-008`; apoyo en `REQ-ESP-007` y `REQ-SOL-005` | Parcial | Solo lista franjas ocupadas; no define franjas libres ni “tiempo real” (H-14, H-36). |
| **N3. Evitar reservas que se crucen en el tiempo** | `REQ-DIS-001` a `REQ-DIS-007`, `REQ-DIS-009`, `REQ-SOL-003`, `REQ-SOL-010`, `REQ-CAN-005` | Alta | La regla y la revalidación están bien cubiertas; queda el riesgo residual de concurrencia en SQLite (H-63). |
| **N4. Controlar quién puede solicitar, aprobar y administrar** | `REQ-USR-001` a `REQ-USR-009`, `REQ-ESP-005`, `REQ-ESP-007`, `REQ-ESP-008`, `REQ-SOL-001`, `REQ-SOL-009`, `REQ-APR-001`, `REQ-APR-005`, `REQ-APR-006`, `REQ-CAN-006` | Parcial | Aprobar y administrar están cubiertos; “quién puede solicitar” no (H-06, H-35). |
| **N5. Registrar el flujo de aprobación o rechazo** | `REQ-APR-001` a `REQ-APR-008`, `REQ-DIS-006`, `REQ-DIS-007`, `REQ-DIS-009`, `REQ-HIS-001` (eventos de aprobación/rechazo) | Alta | La fecha de decisión no tiene fuente estable (H-05, H-58); faltan escenarios de cola y conflicto (H-18, H-19). |
| **N6. Permitir cancelaciones y conservar el historial** | `REQ-CAN-001` a `REQ-CAN-006`, `REQ-HIS-001` a `REQ-HIS-005` | Alta | La inmutabilidad y los filtros son invenciones que deben registrarse (H-29, H-30); no hay relleno histórico (H-59). |
| **N7. Facilitar la administración de usuarios y roles** | `REQ-USR-001` a `REQ-USR-009`, especialmente `REQ-USR-006`, `REQ-USR-007`, `REQ-USR-008` | Alta | No se especifica la creación de usuarios desde la administración (H-61); el cambio de rol necesita precisión (H-11). |
| **N8. Preparar el sistema para nuevas reglas de negocio** | `REQ-BAS-007`, `REQ-DIS-009`; convención de servicios por app | Parcial | La separación solo está asegurada en `reservations`; `accounts` y `spaces` quedan fuera (H-02, H-40). |

**Lectura de la tabla:** N1, N3, N5, N6 y N7 tienen cobertura alta; N2, N4 y N8 tienen cobertura parcial. Las brechas de N2 y N4 son las más relevantes porque son necesidades de prioridad alta en el plan.

---

## 8. Decisiones nuevas respecto al plan que deben registrarse

> El plan 2.4–2.6 y 3.3 no contiene estas decisiones. No se propone eliminarlas: se propone registrarlas en el diseño del cambio correspondiente y en `INFORME_FINAL.md`, con su justificación y su impacto.

### H-52 — Secuencia de `AUTH_USER_MODEL`, reinicio de base y regeneración de la migración inicial

- **Severidad:** alta
- **Descripción:** `usuarios-roles` decide fijar `AUTH_USER_MODEL` después de `base-proyecto` y reiniciar `db.sqlite3`, regenerando la migración inicial de `accounts`. El plan 3.3 exige el usuario personalizado desde la primera migración, pero no autoriza explícitamente a reescribir migraciones ya publicadas.
- **Corrección propuesta:** registrar la decisión con una de dos alternativas: (a) adelantar el usuario personalizado a `base-proyecto`; (b) declarar que la migración inicial de `accounts` es la primera migración real y que `base-proyecto` no se migra hasta que exista. Documentar el borrado de `db.sqlite3` como paso de desarrollo, no como migración de datos.

### H-53 — `TipoEspacio` y `Rol` como `TextChoices` en lugar de modelos o `Group`

- **Severidad:** media
- **Descripción:** El plan 2.3 propone `TipoEspacio` como modelo y `Rol` “o uso de Groups”. Las especificaciones usan `TextChoices` para ambos. Es una decisión de modelado que simplifica el esquema, pero cambia la forma de administrar tipos y roles.
- **Corrección propuesta:** registrar la decisión y su consecuencia: los tipos y roles no se administran como filas; se cambian en código y en migración. Si se requiere administración dinámica, crear el modelo y su CRUD. Actualizar la tabla de modelos del plan o el diseño.

### H-54 — Protección del último administrador y prohibición de autodecisión

- **Severidad:** media
- **Descripción:** Son dos reglas de gobierno nuevas: `REQ-USR-007` impide dejar el sistema sin administrador activo; `REQ-APR-005` impide que un usuario decida su propia solicitud. El plan no las menciona.
- **Corrección propuesta:** registrar ambas con su alcance y sus excepciones. La primera debe coordinarse con el cambio de rol (`REQ-USR-006`); la segunda debe aplicarse a aprobación y rechazo, incluido el administrador, y reflejarse en la cola y en el servicio.

### H-55 — Correo único sin distinguir mayúsculas y contraseña mínima de 8

- **Severidad:** media
- **Descripción:** El plan solo enumera el campo `email`; no fija unicidad, normalización ni política de contraseña.
- **Corrección propuesta:** registrar la decisión y su alcance: correo obligatorio, normalizado a minúsculas, único también en edición; contraseña mínima de 8 caracteres en registro y en creación administrativa. Aclarar si los usuarios de `seed_data` cumplen la política.

### H-56 — Horario operativo configurable

- **Severidad:** media
- **Descripción:** `REQ-SOL-007` introduce un rango 06:00–22:00 configurable en `settings`, ausente del plan.
- **Corrección propuesta:** registrar las claves, el tipo, el valor inicial y la validación de apertura/cierre. Documentar que cambiar el ajuste no requiere migración y que las reservas ya creadas no se reinterpretan.

### H-57 — Límite temporal de cancelación

- **Severidad:** media
- **Descripción:** `REQ-CAN-004` impide cancelar en el instante exacto del inicio o después, con `ahora >= inicio`. El plan 2.5 solo define estados, no tiempos.
- **Corrección propuesta:** registrar la regla exacta y la zona horaria (`America/Bogota`), y la decisión de que el instante exacto cuenta como “ya iniciada”. Añadir la prueba de un minuto antes, instante exacto y después.

### H-58 — Fecha de decisión: `actualizado_en` o campo nuevo

- **Severidad:** media
- **Descripción:** `aprobacion-rechazo` usa `actualizado_en` como fecha de decisión, pero `cancelacion-historial` la sobrescribe. Es una decisión nueva y frágil.
- **Corrección propuesta:** registrar una de dos: añadir `fecha_decision` a `Reserva`; o declarar `HistorialReserva.fecha_evento` como fuente oficial de la fecha de decisión. Actualizar `REQ-APR-002` y sus escenarios en consecuencia.

### H-59 — Semántica del historial: inmutable, sin relleno, con evento de creación y estado anterior nulo

- **Severidad:** media
- **Descripción:** El plan 2.4 define los campos de `HistorialReserva`, pero no decide que el historial sea inmutable, que no se rellene para reservas anteriores, que la creación genere un evento con `estado_anterior = NULL` ni que `reserva` y `actor` usen `PROTECT`.
- **Corrección propuesta:** registrar el conjunto de decisiones como “política de auditoría”: inmutabilidad desde la aplicación, sin backfill, evento de creación, `estado_anterior` nullable, `PROTECT` en las claves foráneas y sin `CheckConstraint` de estados (validación en servicio). Documentar los límites (SQL crudo, `bulk_create`).

### H-60 — Visibilidad y filtros del historial

- **Severidad:** media
- **Descripción:** `REQ-HIS-004` y `REQ-HIS-005` deciden que el solicitante ve solo sus reservas, el administrador todas, el aprobador no ve historial ajeno y el listado se filtra por estado, fecha y espacio. El plan solo dice “consultar todo el historial” para el administrador y “ver su historial” para el solicitante.
- **Corrección propuesta:** registrar el alcance por rol y los filtros como decisiones de privacidad y usabilidad. Aclarar la asimetría con `REQ-SOL-009` (el aprobador ve el detalle pero no el historial) y el comportamiento de los filtros inválidos.

### H-61 — Alcance de la administración de usuarios: no se crean usuarios desde la gestión

- **Severidad:** baja
- **Descripción:** `REQ-USR-006` permite listar, editar, cambiar rol y activar/desactivar, pero la propuesta excluye explícitamente la creación de usuarios desde la administración. El plan 1.3 dice “gestionar usuarios” sin precisar si incluye crear.
- **Corrección propuesta:** registrar que la creación solo ocurre por registro público y `seed_data` en esta versión, y que el administrador no crea cuentas. Si el plan exige creación administrativa, añadir el requisito y la tarea.

### H-62 — Decisiones de validación de espacios y ausencia de eliminación física

- **Severidad:** baja
- **Descripción:** `REQ-ESP-003`/`REQ-ESP-004`/`REQ-ESP-006` deciden unicidad insensible a mayúsculas, capacidad positiva y desactivación lógica sin borrado. El plan solo dice nombre único y menciona el estado activo; no detalla estas reglas.
- **Corrección propuesta:** registrar las tres decisiones y su justificación (conservar historial de reservas, evitar duplicados). Añadir la normalización de nombre (H-09) y la garantía de tipo (H-08) si se aceptan.

### H-63 — Límites de SQLite: `select_for_update` y ausencia de índice por espacio/fecha

- **Severidad:** baja
- **Descripción:** El plan 3.3 ya reconoce que SQLite ignora `select_for_update`; los diseños de `disponibilidad`, `aprobacion` y `cancelacion` lo repiten y deciden mantenerlo para una futura migración a PostgreSQL. También se decide no crear índice por `(espacio, fecha, estado)`.
- **Corrección propuesta:** registrar ambas decisiones en el informe final: la mitigación es transacción + revalidación + actualización condicional, no bloqueo real; el índice se pospone y se medirá si crece el volumen. No presentar la mitigación como equivalente a un bloqueo pesimista.

### H-64 — Alcance de la vista de disponibilidad y de la consulta de franjas

- **Severidad:** baja
- **Descripción:** `REQ-DIS-008` decide que la vista sea para cualquier autenticado, con espacios activos, y que muestre solo franjas ocupadas, sin solicitante ni motivo. El plan no detalla el alcance ni la privacidad.
- **Corrección propuesta:** registrar la decisión y su justificación de privacidad. Si se añade la consulta de una franja concreta (H-36), actualizar el requisito y la vista.

### H-65 — Normalización y longitud del motivo de rechazo

- **Severidad:** baja
- **Descripción:** `REQ-APR-003` decide motivo obligatorio, `strip()` de extremos y ausencia de máximo. El plan 2.5 solo exige “con motivo”.
- **Corrección propuesta:** registrar la decisión de normalización y el carácter ilimitado (o fijar un máximo). Aclarar si se conservan saltos de línea y si el motivo se muestra íntegro en el detalle.

---

## Conclusión

Las especificaciones cubren el núcleo del plan (N1, N3, N5, N6 y N7) con un nivel de detalle adecuado y una buena disciplina de escenarios. Los bloqueos principales antes de implementar son:

1. Resolver la secuencia de `AUTH_USER_MODEL` y la migración inicial (H-01, H-44, H-52).
2. Decidir la política de solicitud para cumplir N4 (H-06, H-35).
3. Definir la disponibilidad más allá del listado de ocupadas para cumplir N2 (H-14, H-36).
4. Corregir la fuente de la fecha de decisión (H-05, H-58).
5. Registrar las decisiones nuevas de gobierno, historial y validaciones (H-25 a H-34, H-54 a H-65).

No se modificó ningún archivo de `openspec/changes` ni se escribió código de la aplicación. Las correcciones propuestas quedan pendientes de aprobación.
