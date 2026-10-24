# Spec Delta

## Purpose

Define la identidad de las personas que usan el sistema: un modelo de usuario
personalizado con roles, registro y autenticación, administración de cuentas por
parte del administrador y un mecanismo centralizado de restricción de acceso por rol
que los demás módulos reutilizan.

## ADDED Requirements

### Requirement: REQ-USR-001 Modelo de usuario personalizado completado desde la primera migración

El sistema SHALL usar el modelo de usuario personalizado `accounts.Usuario` creado
por `base-proyecto` y declarado en `AUTH_USER_MODEL`. Este cambio SHALL completar ese
modelo con los campos de dominio `nombre_completo`, `email` obligatorio y único sin
distinguir mayúsculas, y `rol`, mediante una migración nueva que conserve la
migración inicial ya versionada. Ninguna tabla de usuario anterior SHALL quedar en uso.

#### Scenario: La migración de cuentas completa el usuario personalizado en base limpia

- **GIVEN** una base de datos vacía y la configuración `AUTH_USER_MODEL = "accounts.Usuario"`
- **WHEN** se ejecuta `python manage.py migrate`
- **THEN** el comando termina sin errores
- **AND** existe la tabla del modelo `accounts.Usuario` con las columnas `username`,
  `email`, `nombre_completo`, `rol` y `is_active`
- **AND** no existe la tabla `auth_user` del usuario por defecto de Django

#### Scenario: Los campos de dominio se agregan sin regenerar la migración inicial

- **GIVEN** el cambio `base-proyecto` aplicado con `accounts/migrations/0001_initial.py`
  y su tabla `accounts_usuario`
- **WHEN** se aplica la migración de este cambio
- **THEN** `0001_initial.py` permanece sin cambios
- **AND** una migración posterior agrega `nombre_completo`, `rol` y la restricción
  de unicidad de correo
- **AND** la base de datos existente no necesita borrarse para migrar

#### Scenario: Un usuario guarda y recupera todos sus campos

- **GIVEN** los datos de una persona con usuario, correo, nombre completo y rol `APROBADOR`
- **WHEN** se crea y se guarda el usuario
- **THEN** al recuperarlo se obtienen los mismos valores en `username`, `email`,
  `nombre_completo` y `rol`
- **AND** el usuario queda activo por defecto

#### Scenario: El comando createsuperuser usa el modelo personalizado

- **GIVEN** una base de datos migrada
- **WHEN** se crea un superusuario de forma no interactiva
- **THEN** el registro se almacena como `accounts.Usuario`
- **AND** el usuario puede autenticarse con sus credenciales

### Requirement: REQ-USR-002 Correo único sin distinguir mayúsculas y contraseña mínima

El correo electrónico SHALL ser único sin distinguir mayúsculas de minúsculas y la
contraseña SHALL tener mínimo 8 caracteres. Un registro que incumpla cualquiera de
las dos condiciones SHALL rechazarse sin crear la cuenta.

#### Scenario: Registro con correo repetido falla

- **GIVEN** una cuenta registrada con el correo `ana@ejemplo.com`
- **WHEN** un visitante intenta registrarse con `Ana@Ejemplo.com`
- **THEN** el registro se rechaza con un error asociado al campo de correo
- **AND** no se crea una segunda cuenta

#### Scenario: Registro con contraseña corta falla

- **GIVEN** un visitante en el formulario de registro
- **WHEN** envía una contraseña de 7 caracteres
- **THEN** el registro se rechaza con un error asociado al campo de contraseña
- **AND** no se crea la cuenta

#### Scenario: Registro con contraseña de ocho caracteres es aceptado

- **GIVEN** un visitante con correo no registrado
- **WHEN** envía una contraseña de 8 caracteres o más
- **THEN** la cuenta se crea correctamente

### Requirement: REQ-USR-003 Registro público con rol SOLICITANTE obligatorio

Un visitante SHALL poder registrarse desde el formulario público. Todo usuario
creado por esta vía SHALL recibir el rol `SOLICITANTE`, sin posibilidad de elegir ni
declarar otro rol en la solicitud.

#### Scenario: Registro exitoso asigna SOLICITANTE

- **GIVEN** un visitante anónimo con datos válidos
- **WHEN** completa el registro público
- **THEN** la cuenta se crea con rol `SOLICITANTE`
- **AND** el visitante es dirigido al inicio de sesión con un mensaje de éxito

#### Scenario: El rol enviado por el cliente se ignora

- **GIVEN** un visitante que manipula la solicitud de registro e incluye `rol=ADMINISTRADOR`
- **WHEN** el formulario se procesa
- **THEN** la cuenta se crea con rol `SOLICITANTE`
- **AND** el valor enviado no modifica el rol asignado

### Requirement: REQ-USR-004 Inicio y cierre de sesión con usuario y contraseña

El sistema SHALL permitir iniciar sesión con usuario y contraseña y cerrar la sesión
activa. Tras un inicio de sesión correcto el usuario SHALL ser redirigido al inicio y
la sesión SHALL quedar autenticada; el cierre de sesión SHALL eliminar la sesión.

#### Scenario: Login correcto redirige al inicio

- **GIVEN** un usuario activo con credenciales válidas
- **WHEN** inicia sesión con su usuario y contraseña
- **THEN** la respuesta redirige al inicio
- **AND** la sesión del cliente queda autenticada como ese usuario

#### Scenario: Login con credenciales inválidas muestra error

- **GIVEN** un usuario activo
- **WHEN** intenta iniciar sesión con una contraseña incorrecta
- **THEN** la página de login responde con estado 200
- **AND** muestra un mensaje de error de credenciales
- **AND** la sesión no queda autenticada

#### Scenario: Cierre de sesión termina la sesión

- **GIVEN** un usuario autenticado
- **WHEN** cierra sesión
- **THEN** la sesión deja de estar autenticada
- **AND** la respuesta redirige al inicio

### Requirement: REQ-USR-005 Usuario inactivo no puede iniciar sesión

Un usuario con estado inactivo SHALL NOT poder iniciar sesión, incluso si presenta
credenciales correctas. El intento SHALL rechazarse con un mensaje que indique que la
cuenta no está activa y la sesión SHALL permanecer anónima.

#### Scenario: Usuario inactivo no entra

- **GIVEN** un usuario desactivado cuya contraseña es correcta
- **WHEN** intenta iniciar sesión
- **THEN** la sesión no queda autenticada
- **AND** la respuesta no redirige al inicio autenticado
- **AND** se informa que la cuenta no está activa

### Requirement: REQ-USR-006 Gestión de usuarios por el ADMINISTRADOR

El rol `ADMINISTRADOR` SHALL poder listar los usuarios, editar sus datos, cambiar su
rol y activarlos o desactivarlos. Los cambios SHALL persistir y reflejarse de
inmediato en el acceso del usuario afectado.

#### Scenario: El administrador lista los usuarios

- **GIVEN** un administrador autenticado y usuarios registrados
- **WHEN** abre la gestión de usuarios
- **THEN** la respuesta tiene estado 200
- **AND** el listado incluye a los usuarios con su rol y estado activo

#### Scenario: El administrador cambia el rol de un usuario

- **GIVEN** un administrador autenticado y un usuario con rol `SOLICITANTE`
- **WHEN** el administrador cambia el rol del usuario a `APROBADOR`
- **THEN** el cambio se guarda
- **AND** el usuario afectado queda con rol `APROBADOR`

#### Scenario: El administrador desactiva a un usuario

- **GIVEN** un administrador autenticado y un usuario activo con rol `SOLICITANTE`
- **WHEN** el administrador lo desactiva
- **THEN** el usuario queda inactivo
- **AND** ese usuario ya no puede iniciar sesión

#### Scenario: El administrador edita los datos de un usuario

- **GIVEN** un administrador autenticado y un usuario existente
- **WHEN** el administrador modifica el nombre completo y el correo
- **THEN** los nuevos valores se guardan y se muestran en el listado

### Requirement: REQ-USR-007 Protección del último ADMINISTRADOR activo

El sistema SHALL impedir desactivar o retirar el rol `ADMINISTRADOR` al último
administrador activo, y SHALL rechazar la operación sin modificar la cuenta.

#### Scenario: El administrador intenta desactivar al último administrador y es rechazado

- **GIVEN** exactamente un usuario activo con rol `ADMINISTRADOR`
- **WHEN** se intenta desactivar esa cuenta
- **THEN** la operación se rechaza con un mensaje de error
- **AND** la cuenta permanece activa y conserva el rol `ADMINISTRADOR`

#### Scenario: El administrador intenta cambiar el rol del último administrador activo

- **GIVEN** exactamente un usuario activo con rol `ADMINISTRADOR`
- **WHEN** se intenta cambiar su rol a `APROBADOR`
- **THEN** la operación se rechaza con un mensaje de error
- **AND** la cuenta conserva el rol `ADMINISTRADOR`

#### Scenario: Con dos administradores activos la desactivación es permitida

- **GIVEN** dos usuarios activos con rol `ADMINISTRADOR`
- **WHEN** se desactiva a uno de ellos
- **THEN** la operación se acepta
- **AND** queda al menos un administrador activo

### Requirement: REQ-USR-008 Acceso exclusivo del ADMINISTRADOR a la gestión de usuarios

Solo el rol `ADMINISTRADOR` SHALL acceder a la gestión de usuarios. Un usuario
autenticado sin ese rol SHALL recibir una respuesta 403 y un visitante anónimo SHALL
ser redirigido a la página de inicio de sesión.

#### Scenario: SOLICITANTE intenta abrir la gestión de usuarios y recibe 403

- **GIVEN** un usuario autenticado con rol `SOLICITANTE`
- **WHEN** solicita la ruta de gestión de usuarios
- **THEN** la respuesta tiene estado 403
- **AND** no se muestra ningún dato de las cuentas

#### Scenario: Anónimo es redirigido al login

- **GIVEN** un visitante no autenticado
- **WHEN** solicita la ruta de gestión de usuarios
- **THEN** la respuesta redirige a la página de inicio de sesión
- **AND** la URL de destino incluye la ruta original en el parámetro `next`

#### Scenario: El APROBADOR tampoco accede a la gestión de usuarios

- **GIVEN** un usuario autenticado con rol `APROBADOR`
- **WHEN** solicita la ruta de gestión de usuarios
- **THEN** la respuesta tiene estado 403

### Requirement: REQ-USR-009 Mecanismo centralizado de restricción por rol

El sistema SHALL ofrecer en `accounts` un mecanismo centralizado, en forma de
decorador y de mixin equivalentes, para restringir vistas a uno o varios roles. El
mecanismo SHALL ser reutilizable por los demás módulos sin duplicar la lógica y
SHALL aplicarse en todas las vistas de gestión de usuarios.

#### Scenario: El decorador permite al rol autorizado

- **GIVEN** una vista protegida para `ADMINISTRADOR`
- **WHEN** la solicita un usuario con rol `ADMINISTRADOR`
- **THEN** la vista se ejecuta y responde con estado 200

#### Scenario: El decorador rechaza a un rol no autorizado con 403

- **GIVEN** una vista protegida para `ADMINISTRADOR`
- **WHEN** la solicita un usuario autenticado con rol `SOLICITANTE`
- **THEN** la vista no se ejecuta
- **AND** la respuesta tiene estado 403

#### Scenario: El mecanismo redirige al anónimo al login

- **GIVEN** una vista protegida por el mecanismo centralizado
- **WHEN** la solicita un visitante anónimo
- **THEN** la respuesta redirige al inicio de sesión
- **AND** la sesión no queda autenticada

#### Scenario: El mecanismo es reutilizable fuera de accounts

- **GIVEN** una vista de otro módulo que declara roles autorizados con el mecanismo de `accounts`
- **WHEN** se ejecutan las pruebas de acceso con cada rol
- **THEN** el comportamiento es el mismo que en las vistas de cuentas
- **AND** no se duplica la lógica de comprobación de rol
