# Tasks

Precondición: `base-proyecto` implementado y su suite en verde. Sin esa base no
existen `accounts`, `templates/base.html` ni `seed_data`.

## 1. Modelo de usuario y roles

- [ ] 1.1 Crear `accounts/roles.py` con `Rol(models.TextChoices)` y los valores `SOLICITANTE`, `APROBADOR` y `ADMINISTRADOR`; verificar con `python manage.py shell -c "from accounts.roles import Rol; print(list(Rol))"` que los tres valores se listan.
- [ ] 1.2 Ampliar `accounts/models.py` con `Usuario(AbstractUser)`: `email` obligatorio con `UniqueConstraint(Lower("email"), name="uniq_usuario_email_ci")`, `nombre_completo` (máx. 150), `rol` con opciones y valor por defecto `SOLICITANTE`, `REQUIRED_FIELDS = ["email", "nombre_completo"]`, `get_full_name()` y la propiedad `es_administrador`; verificar con `python manage.py makemigrations accounts --dry-run --verbosity 3` que la migración propuesta agrega los tres campos y la restricción sobre el modelo existente.
- [ ] 1.3 Implementar `UsuarioManager` que normalice el correo a minúsculas en `create_user` y `create_superuser`, y asignarlo con `objects = UsuarioManager()`; verificar en `python manage.py shell` que un usuario creado con `Ana@Ejemplo.com` queda guardado como `ana@ejemplo.com`.
- [ ] 1.4 Verificar que `base-proyecto` ya declaró `AUTH_USER_MODEL = "accounts.Usuario"` en `config/settings.py` y que no hay que cambiarlo; confirmar con `python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model())"` que imprime `accounts.models.Usuario`.
- [ ] 1.5 Implementar `accounts/services.py` con `es_ultimo_administrador_activo(usuario)` y `actualizar_usuario(usuario, *, datos_validados, actor)`, este último dentro de `transaction.atomic()` y lanzando `ValidationError` cuando la operación dejaría el sistema sin administradores activos; verificar con `python manage.py check` que el módulo importa y con la prueba `test_services.py` del grupo 8 que la regla se aplica.

## 2. Migración incremental y base de datos

- [ ] 2.1 Verificar que `base-proyecto` está aplicado (existen `manage.py`, `accounts/`, `accounts/migrations/0001_initial.py` y `templates/base.html`) y que la base migrada no contiene `auth_user`; no es necesario borrar `db.sqlite3`.
- [ ] 2.2 Generar `accounts/migrations/0002_...` con `python manage.py makemigrations accounts`; verificar que `0001_initial.py` permanece sin cambios y que la nueva migración contiene `AddField` para `nombre_completo`, `rol` y `email`, más la restricción `uniq_usuario_email_ci`.
- [ ] 2.3 Revisar que ninguna migración de `spaces` o `reservations` dependa de `auth.User` y que `accounts.0002` dependa de `accounts.0001_initial`; verificar con `python manage.py showmigrations accounts` que ambas migraciones aparecen y con `python manage.py migrate` que se aplican sin errores.
- [ ] 2.4 Comprobar la secuencia completa en base limpia: ejecutar `python manage.py migrate` y verificar código de salida 0, `showmigrations` sin migraciones pendientes y que `makemigrations --check --dry-run` no detecta cambios.
- [ ] 2.5 Verificar el esquema resultante con `python manage.py shell -c "from django.db import connection; print([c.name for c in connection.introspection.get_table_description(connection.cursor(), 'accounts_usuario')])"`; confirmar que incluye `username`, `email`, `nombre_completo`, `rol` e `is_active`, y que `auth_user` no existe.

## 3. Formularios y configuración de autenticación

- [ ] 3.1 Implementar `UsuarioCreationForm(UserCreationForm)` en `accounts/forms.py` con `username`, `email`, `nombre_completo`, `password1` y `password2`; excluir cualquier campo de rol y normalizar el correo en `clean_email`, rechazando duplicados sin distinguir mayúsculas; verificar en `python manage.py shell` que un formulario con correo duplicado en otra capitalización es inválido y que el rol no figura en `form.fields`.
- [ ] 3.2 Implementar `UsuarioAdminForm(ModelForm)` con `username`, `email`, `nombre_completo`, `rol` e `is_active`, sin campos de contraseña ni de staff/superusuario, y hacer que su `save()` invoque `actualizar_usuario` traduciendo el `ValidationError` a un error de formulario; verificar en `python manage.py shell` que un formulario que intenta degradar al último administrador activo no es válido y no modifica la cuenta.
- [ ] 3.3 Implementar la `AuthenticationForm` propia con `confirm_login_allowed` que rechace usuarios inactivos con el mensaje "La cuenta no está activa"; verificar en `python manage.py shell` que un usuario inactivo con contraseña correcta produce `is_valid() == False` y el mensaje esperado.
- [ ] 3.4 Configurar en `config/settings.py` `AUTH_PASSWORD_VALIDATORS` con `MinimumLengthValidator` y `min_length: 8` junto a los validadores de similitud, contraseña común y contraseña numérica; verificar con `python manage.py check` y con un formulario de registro que una contraseña de 7 caracteres es inválida.
- [ ] 3.5 Configurar `LOGIN_URL`, `LOGIN_REDIRECT_URL` y `LOGOUT_REDIRECT_URL` apuntando a `accounts:login` y `core:home`; verificar con `python manage.py shell -c "from django.conf import settings; print(settings.LOGIN_URL, settings.LOGIN_REDIRECT_URL, settings.LOGOUT_REDIRECT_URL)"`.

## 4. Vistas y rutas de cuentas

- [ ] 4.1 Implementar `RegistroView` con `UsuarioCreationForm`, fijando `rol=Rol.SOLICITANTE` en el servidor, redirección a `accounts:login` y mensaje de éxito; verificar en `python manage.py shell` con el cliente de pruebas que un POST con `rol=ADMINISTRADOR` crea la cuenta como `SOLICITANTE` y redirige a login.
- [ ] 4.2 Implementar las vistas de login y logout usando `LoginView`, `LogoutView` y la `AuthenticationForm` propia, con `success_url`/`next_page` según la configuración; verificar que `POST /accounts/login/` con credenciales válidas redirige al inicio y que `POST /accounts/logout/` cierra la sesión.
- [ ] 4.3 Implementar `UsuarioListView` (`ListView`) y `UsuarioUpdateView` (`UpdateView`) con `UsuarioAdminForm`, plantillas y `success_url` al listado; verificar en `python manage.py shell` que el listado devuelve 200 para un administrador autenticado y que la edición guarda los cambios.
- [ ] 4.4 Crear `accounts/urls.py` con los nombres `accounts:login`, `accounts:logout`, `accounts:registro`, `accounts:usuario_lista` y `accounts:usuario_editar`, e incluirlo en `config/urls.py` bajo `accounts/`; verificar con `python manage.py check` y con `python manage.py shell -c "from django.urls import reverse; print(reverse('accounts:login'), reverse('accounts:usuario_lista'))"`.

## 5. Plantillas

- [ ] 5.1 Crear `accounts/templates/accounts/login.html` con el formulario de acceso y el bloque de errores no asociados a campo, y `registro.html` con los campos de usuario, correo, nombre completo y contraseñas; verificar que ambas páginas cargan con estado 200 desde `runserver`.
- [ ] 5.2 Crear `accounts/templates/accounts/usuario_lista.html` con usuario, nombre, correo, rol, estado y enlace de edición, y `usuario_form.html` con el formulario de edición; verificar que el listado muestra los usuarios creados por `seed_data` y que el formulario guarda sin errores.
- [ ] 5.3 Actualizar `templates/base.html` para usar `{% url %}` en los enlaces de login, registro y logout, mostrar el enlace "Usuarios" solo cuando `user.es_administrador` es verdadero, y renderizar el logout como formulario POST con `{% csrf_token %}`; verificar que un anónimo no ve el enlace de usuarios ni de logout, y que un administrador sí los ve.
- [ ] 5.4 Crear `templates/403.html` que extienda `base.html` y explique la falta de permisos; verificar que una petición de un `SOLICITANTE` a la gestión de usuarios muestra esa plantilla con estado 403.

## 6. Mecanismo centralizado de permisos

- [ ] 6.1 Implementar `accounts/permissions.py` con la función interna `usuario_tiene_rol`, el decorador `roles_requeridos(*roles)` y el mixin `RolRequeridoMixin` con `roles_permitidos`; verificar con `python manage.py check` que el módulo importa y con el cliente de pruebas que un anónimo es redirigido al login con `next` y un rol no autorizado recibe 403.
- [ ] 6.2 Aplicar `RolRequeridoMixin` a `UsuarioListView` y `UsuarioUpdateView` con `roles_permitidos = [Rol.ADMINISTRADOR]`; verificar con el cliente de pruebas que `SOLICITANTE` y `APROBADOR` reciben 403, el anónimo redirige al login y el administrador obtiene 200.
- [ ] 6.3 Comprobar la reutilización fuera de `accounts`: importar `roles_requeridos` en una vista de prueba de `spaces/tests/` y verificar que el mecanismo deniega y permite igual que en `accounts` sin duplicar la comprobación.
- [ ] 6.4 Documentar en el docstring de `accounts/permissions.py` el contrato del mecanismo (orden de evaluación, redirección del anónimo, 403 del autenticado sin rol) para que `spaces` y `reservations` lo adopten; verificar que el docstring describe el comportamiento comprobado por las pruebas.

## 7. Datos de ejemplo en seed_data

- [ ] 7.1 Reemplazar la siembra de `Group` en `core/management/commands/seed_data.py` por la siembra de un usuario por rol (`solicitante`, `aprobador`, `admin`) con correos `@ejemplo.com`, rol correspondiente y contraseña de demostración `Demo12345!`; usar `get_or_create(username=...)` y `set_password` solo al crear; verificar que el comando termina con código 0 y reporta creados/existentes.
- [ ] 7.2 Verificar la idempotencia: ejecutar `python manage.py seed_data` dos veces y comprobar con `python manage.py shell -c "from accounts.models import Usuario; print(Usuario.objects.count(), list(Usuario.objects.values_list('username','rol')))"` que el conteo no cambia y hay exactamente un usuario por rol.
- [ ] 7.3 Actualizar `core/tests/test_seed_data.py` para comprobar usuarios en lugar de grupos: dos ejecuciones no duplican registros y existe un usuario por cada valor de `Rol`; verificar con `python manage.py test core.tests.test_seed_data`.
- [ ] 7.4 Documentar las credenciales de demostración en el `help_text` del comando y en su docstring, indicando que son solo para entorno local; verificar con `python manage.py help seed_data` que el texto aparece.

## 8. Pruebas de la capacidad

- [ ] 8.1 Crear `accounts/tests/` con `__init__.py` y `utils.py`, incluyendo un helper `crear_usuario(rol=Rol.SOLICITANTE, activo=True, **datos)`; verificar con `python manage.py test accounts` que el paquete de pruebas se descubre sin errores.
- [ ] 8.2 Escribir `accounts/tests/test_models.py`: campos del usuario personalizado, rol por defecto `SOLICITANTE`, correo único insensible a mayúsculas (`ana@ejemplo.com` vs `Ana@Ejemplo.com`), `get_full_name` y `es_administrador`; verificar con `python manage.py test accounts.tests.test_models` (cubre REQ-USR-001 y REQ-USR-002).
- [ ] 8.3 Escribir `accounts/tests/test_registration.py`: registro exitoso asigna `SOLICITANTE`, correo repetido falla, contraseña de 7 caracteres falla, contraseña de 8 se acepta y el `rol=ADMINISTRADOR` enviado se ignora; verificar con `python manage.py test accounts.tests.test_registration` (cubre REQ-USR-002 y REQ-USR-003).
- [ ] 8.4 Escribir `accounts/tests/test_authentication.py`: login correcto redirige al inicio y autentica la sesión, credenciales inválidas muestran error sin autenticar, usuario inactivo no entra y logout por POST cierra la sesión; verificar con `python manage.py test accounts.tests.test_authentication` (cubre REQ-USR-004 y REQ-USR-005).
- [ ] 8.5 Escribir `accounts/tests/test_services.py`: el servicio rechaza desactivar al último administrador activo, rechaza cambiar su rol y permite la operación cuando hay dos administradores activos; verificar con `python manage.py test accounts.tests.test_services` (cubre REQ-USR-007 a nivel de regla).
- [ ] 8.6 Escribir `accounts/tests/test_user_management.py`: listado, edición de datos, cambio de rol, activación/desactivación, rechazo del último administrador desde la interfaz, 403 para `SOLICITANTE` y `APROBADOR`, y redirección del anónimo con `next`; verificar con `python manage.py test accounts.tests.test_user_management` (cubre REQ-USR-006, REQ-USR-007 y REQ-USR-008).
- [ ] 8.7 Escribir `accounts/tests/test_permissions.py` y la prueba de reutilización en `spaces/tests/test_permissions.py`: el decorador y el mixin permiten al rol autorizado, devuelven 403 al autenticado sin rol y redirigen al anónimo; verificar con `python manage.py test accounts.tests.test_permissions spaces.tests.test_permissions` (cubre REQ-USR-009).
- [ ] 8.8 Ejecutar `python manage.py test` completo junto con `python manage.py check` y `python manage.py makemigrations --check --dry-run`; verificar que toda la suite pasa, que no hay migraciones pendientes y que cada escenario de `specs/usuarios-roles/spec.md` tiene al menos una prueba con el identificador del requisito en su nombre.

## Workflow follow-up

- Revisar los artefactos antes de implementar.
- Implementar este cambio después de `base-proyecto`; no antes.
- Tras las pruebas en verde, archivar el cambio para crear la especificación vigente de `usuarios-roles`.
- Registrar para `spaces` y `reservations` que las claves foráneas a usuarios usan `settings.AUTH_USER_MODEL` y que la protección por rol se importa de `accounts/permissions.py`.
