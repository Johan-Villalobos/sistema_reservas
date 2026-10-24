# Tasks

Precondición: `base-proyecto` y `usuarios-roles-permisos` implementados, con
`accounts.Usuario`, el mecanismo `RolRequeridoMixin` y `seed_data` operativos.

## 1. Modelo de espacio

- [ ] 1.1 Crear `spaces/choices.py` con `TipoEspacio(models.TextChoices)` y los valores `LABORATORIO`, `AUDITORIO` y `SALA_COMPUTO` con sus etiquetas en español; verificar con `python manage.py shell -c "from spaces.choices import TipoEspacio; print(list(TipoEspacio))"` que se listan exactamente tres.
- [ ] 1.2 Implementar `spaces/models.py` con `EspacioAcademico`: `nombre` (máx. 120), `tipo` con opciones, `capacidad` positiva, `ubicacion` (máx. 150), `descripcion` opcional y `activo` por defecto verdadero; verificar con `python manage.py makemigrations spaces --dry-run --verbosity 3` que la migración propuesta incluye los seis campos.
- [ ] 1.3 Agregar a `Meta` la restricción `UniqueConstraint(Lower("nombre"), name="uniq_espacio_nombre_ci")` y el `CheckConstraint(Q(capacidad__gt=0), name="ck_espacio_capacidad_positiva")`, con `ordering = ["nombre"]`; verificar que el dry-run de migración incluye ambas restricciones.
- [ ] 1.4 Implementar `EspacioQuerySet` con `activos()` e `inactivos()` y asignarlo como manager por defecto, y normalizar el nombre en `save()` recortando extremos y colapsando espacios internos; verificar en `python manage.py shell` que `EspacioAcademico.objects.activos()` excluye los inactivos y que guardar `"  Auditorio   Principal "` persiste `"Auditorio Principal"`.
- [ ] 1.5 Implementar `__str__` y la etiqueta legible del tipo según `TipoEspacio`; verificar en `python manage.py shell` que `str(espacio)` devuelve el nombre del espacio.
- [ ] 1.6 Implementar en `spaces/services.py` las funciones `normalizar_nombre`, `crear_espacio`, `actualizar_espacio` y `desactivar_espacio`, concentrando la normalización, la detección de duplicados sin distinguir mayúsculas y la validación de capacidad; verificar en `python manage.py shell` que crear con `"  Auditorio   Principal "` persiste `"Auditorio Principal"`, que un duplicado lanza un error de validación y que una capacidad de 0 se rechaza sin depender de la vista.

## 2. Migración

- [ ] 2.1 Generar `spaces/migrations/0001_initial.py` con `python manage.py makemigrations spaces`; verificar que el archivo contiene `CreateModel`, el índice funcional de nombre y el `CHECK` de capacidad.
- [ ] 2.2 Aplicar `python manage.py migrate` y verificar código de salida 0 y la tabla `spaces_espacioacademico` con `python manage.py shell -c "from django.db import connection; print([c.name for c in connection.introspection.get_table_description(connection.cursor(), 'spaces_espacioacademico')])"`.
- [ ] 2.3 Comprobar la restricción de unicidad insensible a mayúsculas y el `CHECK` de capacidad con `python manage.py shell`, intentando guardar `"AUDITORIO PRINCIPAL"` cuando existe `"Auditorio Principal"` y una capacidad de 0; verificar que ambas operaciones fallan con `IntegrityError`.
- [ ] 2.4 Verificar la reproducibilidad en base limpia: eliminar `db.sqlite3`, ejecutar `python manage.py migrate` y confirmar código 0, `showmigrations` sin pendientes y `python manage.py makemigrations --check --dry-run` sin cambios detectados.

## 3. Formularios

- [ ] 3.1 Implementar `EspacioForm(ModelForm)` en `spaces/forms.py` con `nombre`, `tipo`, `capacidad`, `ubicacion` y `descripcion`, widgets con clases de Bootstrap y etiquetas en español; verificar que `activo` no figura en `form.fields` y que el formulario renderiza en el servidor de desarrollo.
- [ ] 3.2 Implementar `clean_nombre`: recortar y colapsar espacios, y rechazar duplicados sin distinguir mayúsculas excluyendo la instancia en edición; verificar en `python manage.py shell` con un formulario de creación duplicado y uno de edición sobre el mismo registro (este último debe ser válido).
- [ ] 3.3 Implementar `clean_capacidad` rechazando valores menores que 1; verificar en `python manage.py shell` que los formularios con capacidad 0, -5 y 1.5 son inválidos con error en el campo capacidad.
- [ ] 3.4 Verificar el rechazo de tipo inválido: enviar un valor fuera de `TipoEspacio` al formulario y comprobar en `python manage.py shell` que `is_valid()` es falso y el error aparece en el campo tipo.

## 4. Vistas y rutas

- [ ] 4.1 Implementar `EspacioListView(LoginRequiredMixin, ListView)`: administrador ve todos los espacios, los demás roles solo activos, con filtro por `?tipo=` válido e ignorando valores inválidos; verificar con el cliente de pruebas que un solicitante no ve inactivos y que el filtro `LABORATORIO` no devuelve otros tipos.
- [ ] 4.2 Implementar `EspacioDetailView(LoginRequiredMixin, DetailView)` con queryset de todos los espacios para administrador y solo activos para el resto; verificar que un solicitante recibe 404 en un espacio inactivo y 200 en uno activo.
- [ ] 4.3 Implementar `EspacioCreateView` y `EspacioUpdateView` con `RolRequeridoMixin`, `roles_permitidos = [Rol.ADMINISTRADOR]`, `EspacioForm` y redirección al detalle, delegando la persistencia en `crear_espacio`/`actualizar_espacio`; verificar con el cliente de pruebas que el administrador crea y edita, que un solicitante recibe 403 y que un anónimo redirige al login.
- [ ] 4.4 Implementar `EspacioDesactivarView` solo para POST, con `RolRequeridoMixin`, que invoque `desactivar_espacio`, emita un mensaje y redirija al listado; verificar que un GET devuelve 405, que el registro sigue existiendo tras el POST y que una segunda desactivación no produce error.
- [ ] 4.5 Crear `spaces/urls.py` con los nombres `spaces:espacio_lista`, `spaces:espacio_detalle`, `spaces:espacio_crear`, `spaces:espacio_editar` y `spaces:espacio_desactivar`, e incluirlo en `config/urls.py` bajo `espacios/`; verificar con `python manage.py check` y con `reverse` de cada nombre.
- [ ] 4.6 Confirmar que no existe ninguna ruta ni vista de eliminación física; verificar que `reverse("spaces:espacio_eliminar")` lanza `NoReverseMatch` y que no hay `DeleteView` en `spaces/views.py`.

## 5. Plantillas

- [ ] 5.1 Crear `spaces/templates/spaces/espacio_lista.html` con selector de filtro por tipo, tabla o tarjetas con nombre, tipo, capacidad, ubicación y estado, botón de creación solo para administrador y acciones de editar y desactivar solo para administrador; verificar que el filtro conserva el tipo seleccionado y que un solicitante no ve acciones de administración.
- [ ] 5.2 Crear `spaces/templates/spaces/espacio_detalle.html` con todos los campos del espacio, insignia de estado y acciones de administración cuando corresponda; verificar que muestra ubicación y descripción y que no ofrece eliminar.
- [ ] 5.3 Crear `spaces/templates/spaces/espacio_form.html` reutilizable para crear y editar, con errores por campo y botones de guardar y cancelar; verificar que los errores de nombre y capacidad se muestran junto a su campo.
- [ ] 5.4 Crear `spaces/templates/spaces/espacio_confirmar_desactivar.html` con el nombre del espacio, la advertencia de que dejará de estar disponible y un formulario POST con `{% csrf_token %}`; verificar que cancelar vuelve al detalle sin modificar el estado.
- [ ] 5.5 Actualizar `templates/base.html` para enlazar "Espacios" con `{% url 'spaces:espacio_lista' %}` visible solo para usuarios autenticados; verificar que un anónimo no ve el enlace y que un usuario autenticado navega al catálogo sin errores.

## 6. Datos de ejemplo en seed_data

- [ ] 6.1 Agregar `sembrar_espacios()` a `core/management/commands/seed_data.py` con un `LABORATORIO` (30), un `AUDITORIO` (200) y una `SALA_COMPUTO` (40), usando `get_or_create(nombre=...)` y sin sobrescribir registros existentes; verificar que el comando termina con código 0 y reporta creados y existentes.
- [ ] 6.2 Verificar la idempotencia: ejecutar `python manage.py seed_data` dos veces y comprobar con `python manage.py shell -c "from spaces.models import EspacioAcademico; print(EspacioAcademico.objects.count(), list(EspacioAcademico.objects.values_list('nombre','tipo')))"` que el conteo no cambia y hay un espacio por tipo.
- [ ] 6.3 Verificar que `seed_data` respeta un espacio desactivado por el administrador: desactivar uno de los sembrados, ejecutar de nuevo el comando y comprobar que sigue inactivo y no se duplica.
- [ ] 6.4 Crear `spaces/tests/test_seed_data.py` para comprobar un espacio por tipo y que dos ejecuciones no duplican espacios; conservar en `core/tests/test_seed_data.py` solo las comprobaciones de usuarios y verificar con `python manage.py test spaces.tests.test_seed_data core.tests.test_seed_data`.
- [ ] 6.5 Escribir en `spaces/tests/test_services.py` las pruebas de `crear_espacio`, `actualizar_espacio` y `desactivar_espacio`; verificar con `python manage.py test spaces.tests.test_services` que las reglas se cumplen sin cliente HTTP.

## 7. Pruebas de la capacidad

- [ ] 7.1 Crear `spaces/tests/__init__.py` y `spaces/tests/utils.py` con el helper `crear_espacio(nombre="Laboratorio A", tipo=TipoEspacio.LABORATORIO, capacidad=25, activo=True, **datos)`; verificar con `python manage.py test spaces` que el paquete se descubre sin errores.
- [ ] 7.2 Escribir `spaces/tests/test_models.py`: campos y valor activo por defecto, normalización de nombre, unicidad insensible a mayúsculas, rechazo de capacidad no positiva, queryset `activos()` y `__str__`; verificar con `python manage.py test spaces.tests.test_models` (cubre REQ-ESP-001, REQ-ESP-003 y REQ-ESP-004).
- [ ] 7.3 Escribir `spaces/tests/test_forms.py`: creación válida, tipo inválido, capacidad 0, negativa y decimal, nombre duplicado al crear y al renombrar, y edición válida; verificar con `python manage.py test spaces.tests.test_forms` (cubre REQ-ESP-002, REQ-ESP-003 y REQ-ESP-004).
- [ ] 7.4 Escribir `spaces/tests/test_views.py` (catálogo y detalle): filtro por tipo, solicitante sin inactivos, administrador con inactivos, detalle 200 de activo, detalle 404 de inexistente, detalle 404 de inactivo para solicitante, y redirección al login de anónimo con `next` en listado, detalle y creación; verificar con `python manage.py test spaces.tests.test_views` (cubre REQ-ESP-007 y REQ-ESP-008).
- [ ] 7.5 Ampliar `spaces/tests/test_views.py` (administración): 403 de solicitante y aprobador en crear, editar y desactivar; creación y edición por administrador; desactivación con persistencia del registro; ausencia de ruta de eliminación; verificar con `python manage.py test spaces.tests.test_views` (cubre REQ-ESP-001, REQ-ESP-005 y REQ-ESP-006).
- [ ] 7.6 Ejecutar `python manage.py test` completo, `python manage.py check` y `python manage.py makemigrations --check --dry-run`; verificar que la suite pasa, no hay migraciones pendientes y cada escenario de `specs/espacios/spec.md` tiene al menos una prueba cuyo nombre incluye el identificador del requisito.
- [ ] 7.7 Verificar que las vistas no contienen reglas de negocio propias: revisar que `spaces/views.py` solo valida el formulario e invoca `spaces/services.py`, y que las pruebas de las reglas se ejecutan sin cliente HTTP.

## Workflow follow-up

- Revisar los artefactos antes de implementar.
- Implementar después de `base-proyecto` y `usuarios-roles-permisos`.
- Tras las pruebas en verde, archivar el cambio para crear la especificación vigente de `espacios`.
- Registrar para `reservations` que la clave foránea al espacio debe usar `on_delete=PROTECT` y que las solicitudes solo aplican a espacios activos.
