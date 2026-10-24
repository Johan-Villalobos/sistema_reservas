# Design

## Context

Ver `proposal.md` — Why. El cambio `base-proyecto` define la fundación (proyecto
Django, apps, `templates/base.html`, el usuario mínimo `accounts.Usuario` con
`AUTH_USER_MODEL` ya fijado, los módulos `accounts/services.py`,
`spaces/services.py` y `reservations/services.py` vacíos, y `seed_data` con grupos
provisionales) y aún no está implementado: sus tareas están en 0/26. Este diseño
asume que `base-proyecto` se aplica antes y hereda sus convenciones:

- Raíz del repositorio con `manage.py` y paquete `config/`.
- Plantilla base global en `templates/base.html`, plantillas de app en
  `<app>/templates/<app>/`.
- Navegación construida con `user.is_authenticated` y enlaces de cuentas todavía sin
  rutas nombradas.
- `seed_data` en `core/management/commands/seed_data.py`, idempotente, hoy sembrando
  los grupos `Solicitante`, `Aprobador` y `Administrador` como datos provisionales.
- Base de datos SQLite local, `USE_TZ` activo, `LANGUAGE_CODE = "es-co"`.

Restricción heredada de `base-proyecto/design.md` (decisión 5): `accounts/migrations/
0001_initial.py` ya crea `accounts.Usuario` y `AUTH_USER_MODEL` ya apunta a él. Este
cambio no regenera esa migración: agrega los campos de dominio con una migración
nueva y reemplaza la siembra provisional de grupos por la siembra de usuarios.

## Goals / Non-Goals

**Goals:**

- Introducir el usuario personalizado y los tres roles como única fuente de verdad
  de identidad y autorización.
- Cubrir registro, login, logout y administración de cuentas con pruebas que
  reproduzcan literalmente cada escenario de la especificación.
- Dejar un mecanismo de autorización por rol que `spaces` y `reservations` importen
  sin copiar lógica.

**Non-Goals:**

- No se implementa recuperación de contraseña, verificación de correo, login por
  email ni autenticación externa.
- No se implementa autoservicio de perfil ni cambio de contraseña por el usuario.
- No se crean usuarios desde la gestión administrativa; el alcance es listar,
  editar, cambiar rol y activar/desactivar cuentas existentes.
- No se añaden permisos granulares por objeto ni bitácora de auditoría.
- No se modifican los modelos de espacios ni de reservas.

## Decisions

### 1. `accounts.Usuario` completa el modelo existente con `email` único insensible a mayúsculas

`accounts/models.py` parte del `Usuario(AbstractUser)` mínimo creado por
`base-proyecto` y le agrega:

- `email`: `EmailField` propio, obligatorio y con restricción funcional
  `UniqueConstraint(Lower("email"), name="uniq_usuario_email_ci")`.
- `nombre_completo`: `CharField(max_length=150)`.
- `rol`: `CharField(max_length=12, choices=Rol.choices, default=Rol.SOLICITANTE)`.
- `is_active`: heredado de `AbstractUser`; en la interfaz se muestra como "activo" y
  es el campo que usa Django para bloquear el login.
- `USERNAME_FIELD = "username"`, `REQUIRED_FIELDS = ["email", "nombre_completo"]`.

Los tres campos nuevos y la restricción se agregan con
`accounts/migrations/0002_...`, que depende de `0001_initial` de `base-proyecto`.

- **Motivo**: `AbstractUser` aporta `username`, hash de contraseña, `is_active`,
  `is_staff` y el gestor de usuarios, evitando reimplementar autenticación. La
  restricción funcional sobre `Lower("email")` garantiza unicidad insensible a
  mayúsculas incluso si se escribe por ORM, no solo desde el formulario.
- **Normalización**: un `UsuarioManager` propio convierte el correo a minúsculas en
  `create_user` y `create_superuser`; el formulario de registro y el de edición
  también normalizan antes de guardar, para que la restricción nunca dependa del
  formato de entrada.
- **Alternativa descartada**: `email = EmailField(unique=True)` sin restricción
  funcional. La unicidad sería sensible a mayúsculas y permitiría duplicados
  `ana@x.com` / `Ana@X.com`.
- **Alternativa descartada**: modelo de usuario desde cero (`AbstractBaseUser`).
  Obliga a implementar gestor, permisos y compatibilidad con `admin` sin beneficio
  para el alcance.
- **Alternativa descartada**: `Rol` como `Group` de Django. Ya se descartó en
  `base-proyecto` al elegir un campo `rol`; los grupos añaden joins y permisos por
  objeto que el sistema no requiere.

`nombre_completo` se agrega como campo propio en lugar de componer
`first_name`/`last_name`, que quedan sin uso, porque el requisito y las pantallas
trabajan con un nombre completo único. `get_full_name()` se sobrescribe para
devolver `nombre_completo`.

### 2. Roles como `TextChoices` en `accounts/roles.py`

```text
class Rol(models.TextChoices):
    SOLICITANTE = "SOLICITANTE", "Solicitante"
    APROBADOR   = "APROBADOR",   "Aprobador"
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
```

- **Motivo**: el módulo se importa desde modelos, formularios, servicios y
  decoradores sin riesgo de importación circular; los valores en mayúsculas son los
  que exige la especificación y los que quedan persistidos.
- **Alternativa descartada**: constantes sueltas en `models.py`. Obligan a importar
  modelos en módulos de permisos que no los necesitan.

### 3. Validación de contraseña con los validadores de Django, mínimo 8 explícito

`AUTH_PASSWORD_VALIDATORS` conserva `UserAttributeSimilarityValidator`,
`CommonPasswordValidator` y `NumericPasswordValidator`, y declara explícitamente
`MinimumLengthValidator` con `min_length: 8`.

- **Motivo**: REQ-USR-002 exige el mínimo y el registro debe rechazar contraseñas
  cortas en el formulario, no solo en la creación programática.
- **Alternativa descartada**: validación manual con `len()` en el formulario. Se
  salta al crear usuarios por `createsuperuser` o por código y duplica mensajes.

### 4. Registro público con rol fijado en el servidor

`accounts/forms.py` define `UsuarioCreationForm(UserCreationForm)` con campos
`username`, `email`, `nombre_completo`, `password1` y `password2`. El rol **no** es
un campo del formulario y el `rol` enviado por el cliente se descarta porque el
formulario no lo declara y la vista lo fija explícitamente.

La vista `RegistroView(CreateView)` guarda con `rol=Rol.SOLICITANTE`, redirige a
`accounts:login` y emite un mensaje de éxito.

- **Motivo**: la asignación de rol ocurre en el servidor, a prueba de manipulación
  del POST; cumple REQ-USR-003.
- **Alternativa descartada**: autenticar automáticamente tras el registro. Añade una
  ruta de login implícita y dificulta probar el mensaje de éxito; se prefiere el
  inicio de sesión explícito.
- **`clean_email`**: además de la restricción de base de datos, el formulario
  normaliza a minúsculas y comprueba duplicados para devolver un mensaje claro en
  lugar del error genérico de restricción.

### 5. Login y logout con vistas de Django, logout solo por POST

- `accounts/views.py` define `LoginView` con una `AuthenticationForm` propia que
  sobrescribe `confirm_login_allowed` para devolver el mensaje "La cuenta no está
  activa" cuando `is_active` es falso. Django ya rechaza usuarios inactivos en
  `ModelBackend`, pero el mensaje explícito cumple REQ-USR-005 y evita filtrar si la
  contraseña era correcta.
- `LogoutView` estándar (solo POST desde Django 5) con
  `LOGOUT_REDIRECT_URL = reverse_lazy("core:home")`.
- `LOGIN_URL = reverse_lazy("accounts:login")` y
  `LOGIN_REDIRECT_URL = reverse_lazy("core:home")`.
- La plantilla base renderiza el cierre de sesión como formulario POST con
  `{% csrf_token %}`, no como enlace GET.

- **Motivo**: comportamiento nativo, seguro frente a CSRF y con sesiones de Django;
  el POST obligatorio en logout evita cierres de sesión por prefetch o crawlers.
- **Trade-off**: un enlace `<a>` a logout devolvería 405; se resuelve en la plantilla
  base y se documenta en las pruebas.

### 6. Invariante del último administrador en `accounts/services.py`

`accounts/services.py` concentra la regla:

- `es_ultimo_administrador_activo(usuario)`: verdadero si el usuario es
  `ADMINISTRADOR` activo y no existe otro administrador activo.
- `actualizar_usuario(usuario, *, datos_validados, actor)`: dentro de
  `transaction.atomic()`, aplica los cambios y lanza `ValidationError` si la
  operación dejaría el sistema sin administradores activos.

El `UsuarioAdminForm` llama al servicio en `save()` y traduce el error a un mensaje
de formulario; la vista solo orquesta.

- **Motivo**: REQ-BAS-007 exige que cada aplicación de dominio aísle sus reglas en
  su propio `services.py` y que las vistas solo orquesten. El mismo principio se
  aplica a cuentas con `accounts/services.py`; la regla queda aislada y comprobable
  sin cliente HTTP.
- **Alternativa descartada**: validar solo en `clean()` del formulario. Protege la
  ruta web pero no cualquier llamada futura al ORM ni un `admin` de Django.
- **Alternativa descartada**: `CheckConstraint` en base de datos. Requiere consultar
  el resto de filas, algo que una restricción de fila no puede expresar.
- **Concurrencia**: SQLite no ofrece bloqueo de filas efectivo, igual que en el
  riesgo R8 del plan. Se usa `transaction.atomic()` y recuento dentro de la
  transacción; la limitación se documenta y las pruebas cubren la secuencia normal.

La protección aplica tanto a desactivar como a cambiar el rol del último
administrador activo, porque ambas operaciones producen el mismo estado inválido.

### 7. Mecanismo centralizado de autorización en `accounts/permissions.py`

- `roles_requeridos(*roles)` — decorador para vistas basadas en función.
- `RolRequeridoMixin` — mixin para vistas basadas en clase, con atributo
  `roles_permitidos`.

Comportamiento común, en este orden:

1. Si el usuario no está autenticado → `redirect_to_login(request.get_full_path())`
   con el parámetro `next`.
2. Si está autenticado pero su rol no está en la lista → `PermissionDenied`
   (respuesta 403).

Ambos se apoyan en una función interna `usuario_tiene_rol(usuario, roles)` para no
duplicar la comprobación.

- **Motivo**: REQ-USR-009 pide un único punto de verdad reutilizable; `spaces` y
  `reservations` lo importarán en sus propios cambios.
- **Alternativa descartada**: `permission_required` con permisos de Django. Modela
  permisos por acción y no el rol único del dominio; obligaría a crear permisos
  artificiales.
- **Alternativa descartada**: `UserPassesTestMixin` repetido en cada vista. Duplica
  la lógica y permite divergencias entre módulos.
- **Implementación base**: `RolRequeridoMixin` se apoya en `AccessMixin` para heredar
  `raise_exception`, `permission_denied_message` y el manejo de `next`, y reutiliza
  la misma comprobación que el decorador.

Se añade `templates/403.html` que extiende `base.html` para que el rechazo por rol
tenga una página coherente con el resto del sitio.

### 8. Gestión de usuarios con CBV y formulario acotado

Rutas en `accounts/urls.py`, incluidas desde `config/urls.py` bajo `accounts/`:

| Ruta | Nombre | Vista | Protección |
|---|---|---|---|
| `login/` | `accounts:login` | `LoginView` propia | pública |
| `logout/` | `accounts:logout` | `LogoutView` | autenticado (POST) |
| `registro/` | `accounts:registro` | `RegistroView` | pública |
| `usuarios/` | `accounts:usuario_lista` | `UsuarioListView` | `ADMINISTRADOR` |
| `usuarios/<int:pk>/editar/` | `accounts:usuario_editar` | `UsuarioUpdateView` | `ADMINISTRADOR` |

`UsuarioAdminForm` expone solo `username`, `email`, `nombre_completo`, `rol` e
`is_active`; no permite editar contraseñas ni `is_staff`/`is_superuser`. La
plantilla de listado muestra usuario, nombre, correo, rol, estado y enlace de
edición, e incluye el aviso cuando la cuenta es el último administrador activo.

- **Motivo**: acotar los campos evita escaladas de privilegios accidentales desde la
  interfaz y mantiene la gestión simple.
- **Alternativa descartada**: `admin` de Django como interfaz de gestión. El plan
  pide una interfaz web propia con Bootstrap y roles del dominio; `admin` queda solo
  como utilidad de desarrollo, sin registrarse el modelo.

### 9. Navegación y plantillas

`templates/base.html` pasa a usar rutas nombradas (`{% url %}`) para login, registro
y logout. El enlace "Usuarios" se muestra solo si `user.rol == "ADMINISTRADOR"`, y el
usuario autenticado ve su nombre completo.

- **Motivo**: el cambio base dejó `href` textuales porque las rutas no existían;
  ahora se enlazan nombres para no romper enlaces al mover rutas.
- **Alternativa descartada**: comparar el rol en la plantilla con lógica duplicada;
  se expone la propiedad `Usuario.es_administrador` y la plantilla la consume.

### 10. `seed_data` con un usuario por rol, idempotente

`core/management/commands/seed_data.py` deja de sembrar `Group` y siembra:

| Usuario | Correo | Rol | Contraseña de demo |
|---|---|---|---|
| `solicitante` | `solicitante@ejemplo.com` | `SOLICITANTE` | `Demo12345!` |
| `aprobador` | `aprobador@ejemplo.com` | `APROBADOR` | `Demo12345!` |
| `admin` | `admin@ejemplo.com` | `ADMINISTRADOR` | `Demo12345!` |

Cada usuario se crea con `get_or_create(username=...)`; la contraseña se fija con
`set_password` solo cuando la cuenta se crea, y los datos existentes no se
sobrescriben para no revertir cambios hechos por el administrador. El comando
imprime creados y existentes.

- **Motivo**: REQ-USR-008 de este cambio y la expectativa del plan (3.3) de tener
  usuarios de prueba; la idempotencia de REQ-BAS-008 se conserva porque el conteo de
  usuarios no cambia en la segunda ejecución.
- **Alternativa descartada**: mantener grupos y usuarios a la vez. El rol ya es un
  campo; los grupos quedarían como datos muertos y confundirían la autorización.
- **Trade-off**: contraseñas conocidas en el repositorio. Son cuentas de
  demostración en SQLite local, se documentan como tales y no deben usarse en
  producción.
- **Impacto en pruebas base**: `core/tests/test_seed_data.py` espera grupos; se
  actualiza para verificar usuarios y la idempotencia por `username`.

### 11. Secuencia de migraciones sin reiniciar la base de datos

Como `base-proyecto` ya versiona `accounts/migrations/0001_initial.py` con el
`Usuario` mínimo y `AUTH_USER_MODEL` ya apunta a `accounts.Usuario`, la
implementación:

1. Mantiene `accounts/migrations/0001_initial.py` sin cambios.
2. Agrega `accounts/migrations/0002_...` con `AddField` para `nombre_completo`,
   `rol` y `email`, más la restricción `uniq_usuario_email_ci`.
3. Ejecuta `migrate` sobre la base existente y verifica que no quedan migraciones
   pendientes.

- **Motivo**: la migración inicial ya crea el usuario personalizado, de modo que el
  esquema nunca contiene `auth_user` que haya que descartar. Regenerar `0001`
  rompería la dependencia anunciada a los cambios posteriores y obligaría a borrar
  la base de desarrollo sin necesidad.
- **Alternativa descartada**: borrar `db.sqlite3` y regenerar todas las migraciones.
  No aporta nada cuando la migración inicial correcta ya existe y convierte un paso
  opcional de desarrollo en un requisito del cambio.
- **Alternativa descartada**: editar `0001_initial.py` para incluir los campos de
  dominio. Rompe el historial de migraciones ya compartido con el cambio base.

### 12. Pruebas: un escenario, una prueba

`accounts/tests/` se organiza por área, con `TestCase` y `reverse`:

- `test_models.py`: campos, rol por defecto, unicidad de correo insensible a
  mayúsculas, `get_full_name`.
- `test_registration.py`: registro exitoso, correo repetido, contraseña corta, rol
  enviado por el cliente ignorado.
- `test_authentication.py`: login correcto, credenciales inválidas, inactivo, logout.
- `test_permissions.py`: decorador y mixin con admin, solicitante y anónimo; vista de
  prueba en `spaces/tests/` que reutiliza el mecanismo.
- `test_user_management.py`: listado, edición, cambio de rol, activación y
  desactivación, 403 para roles sin permiso, redirección del anónimo, y las dos
  variantes del último administrador activo.
- `test_services.py`: regla del último administrador a nivel de servicio.
- `core/tests/test_seed_data.py` actualizado: dos ejecuciones de `seed_data` no
  duplican usuarios y existe uno por rol.

Se usa un helper `crear_usuario(rol=..., activo=...)` en `accounts/tests/utils.py`
para evitar duplicar la creación en cada archivo.

- **Motivo**: el plan 5.3 exige que cada escenario se convierta en al menos una
  prueba y que los nombres incluyan el identificador del requisito.
- **Alternativa descartada**: pruebas solo de extremo a extremo. No aíslan la regla
  del último administrador ni el mecanismo de permisos.

## Risks / Trade-offs

- **Dependencia de `base-proyecto`** → este cambio se implementa después; si el
  cambio base aún no se ha aplicado, sus tareas fallan. Se registra como
  precondición explícita en `tasks.md`.
- **Cambio de `AUTH_USER_MODEL` con base ya migrada** → no aplica: `base-proyecto`
  ya declara `AUTH_USER_MODEL = "accounts.Usuario"` y crea `0001_initial`. Este
  cambio solo agrega `0002` y se verifica con `migrate` sobre base limpia.
- **Restricción funcional `Lower(email)` en SQLite** → requiere soporte de índices
  por expresión, disponible en las versiones que acompañan a Python 3.12. Si
  fallara, la alternativa es normalizar y usar `unique=True` con validación
  adicional; se comprueba en la prueba de migración.
- **Carrera al validar el último administrador** → `transaction.atomic()` y recuento
  dentro de la transacción; SQLite no bloquea filas, limitación ya documentada (R8)
  y aceptada para el alcance académico.
- **Logout solo por POST** → la plantilla base debe usar formulario; un enlace GET
  daría 405. Se cubre con la prueba de logout y con revisión de la plantilla.
- **Contraseñas de demostración conocidas** → solo entorno local; se documentan como
  credenciales de prueba y se recomienda cambiarlas en cualquier despliegue.
- **Correo sin verificación** → un visitante puede registrarse con un correo ajeno.
  Aceptado: la verificación por correo está fuera del alcance y el plan excluye el
  envío de correos reales en la primera versión.
- **Actualización de pruebas de `base-proyecto`** → `test_seed_data.py` cambia de
  grupos a usuarios; se ejecuta la suite completa para detectar cualquier otra
  dependencia de los grupos.

## Migration Plan

1. Confirmar que `base-proyecto` está implementado y su suite en verde.
2. Crear `accounts/roles.py` y ampliar `accounts/models.py` (`Usuario`,
   `UsuarioManager`) con los campos de dominio; implementar `accounts/services.py`.
3. Ajustar validadores de contraseña y URLs de login/logout en `config/settings.py`,
   conservando el `AUTH_USER_MODEL` ya configurado.
4. Generar `accounts/migrations/0002_...`; ejecutar `migrate` sobre la base existente
   y verificar que la tabla del usuario personalizado ya existe y queda completa.
5. Implementar formularios, vistas, `accounts/urls.py` y el mecanismo de permisos;
   incluir las rutas en `config/urls.py`.
6. Crear las plantillas `login.html`, `registro.html`, `usuario_lista.html`,
   `usuario_form.html`, `403.html` y actualizar `base.html`.
7. Ampliar `seed_data` con un usuario por rol y actualizar
   `core/tests/test_seed_data.py`.
8. Escribir la suite `accounts/tests/` y ejecutar `python manage.py test` completa.

**Rollback**: revertir el commit y volver a migrar con el estado anterior. Al no
existir datos productivos, no hay pérdida de información.

## Open Questions

Ninguna que afecte las especificaciones, el enfoque o el desglose de tareas. Los
valores concretos de correos y contraseñas de demostración quedan fijados en la
decisión 10 y pueden ajustarse sin cambiar requisitos.
