# Design

## Context

Ver `proposal.md` — Why. Este cambio se apoya en dos cambios previos que aún no están
implementados: `base-proyecto` (proyecto Django, apps, `templates/base.html`,
`seed_data` en `core`) y `usuarios-roles-permisos` (modelo `accounts.Usuario`, roles
`SOLICITANTE`/`APROBADOR`/`ADMINISTRADOR`, mecanismo `roles_requeridos` /
`RolRequeridoMixin`). Convenciones heredadas relevantes:

- Plantillas de app en `<app>/templates/<app>/`; plantilla base global.
- Navegación con rutas nombradas y enlace "Espacios" ya previsto para usuarios
  autenticados.
- Mecanismo único de autorización por rol: anónimo → login con `next`;
  autenticado sin rol → 403.
- `AUTH_USER_MODEL = "accounts.Usuario"`; las claves foráneas futuras a usuarios
  deben usar `settings.AUTH_USER_MODEL`.
- `seed_data` idempotente por clave natural; hoy siembra usuarios de demostración
  tras el cambio de cuentas.
- Cada aplicación de dominio expone sus reglas en su propio `services.py`; `spaces/
  services.py` ya existe como módulo vacío y este cambio lo completa.

El plan 2.4 propone `TipoEspacio` como modelo principal. Este diseño lo sustituye por
un `TextChoices`, decisión explicada en la sección de decisiones.

## Goals / Non-Goals

**Goals:**

- Modelar el espacio con las restricciones de nombre y capacidad garantizadas también
  a nivel de base de datos, no solo en el formulario.
- Cubrir la desactivación lógica como única salida del catálogo, sin rutas de borrado.
- Reutilizar el mecanismo de permisos de `accounts` sin modificarlo ni duplicarlo.
- Dejar un catálogo listo para que `reservations` referencie espacios activos e
  inactivos sin romper historial.

**Non-Goals:**

- No se implementa reactivación de espacios inactivos, edición masiva ni borrado
  físico.
- No se implementa disponibilidad, franjas horarias ni reservas.
- No se agregan imágenes, equipamiento, aforo por configuración ni atributos
  adicionales fuera de los seis campos del requisito.
- No se pagina el listado ni se agrega búsqueda por texto; solo filtro por tipo.

## Decisions

### 1. `EspacioAcademico` con seis campos y estado activo por defecto

`spaces/models.py`:

| Campo | Tipo | Regla |
|---|---|---|
| `nombre` | `CharField(max_length=120)` | único sin distinguir mayúsculas |
| `tipo` | `CharField(max_length=15, choices=TipoEspacio.choices)` | uno de los tres valores |
| `capacidad` | `PositiveIntegerField()` | entero mayor que cero |
| `ubicacion` | `CharField(max_length=150)` | obligatorio |
| `descripcion` | `TextField(blank=True)` | opcional |
| `activo` | `BooleanField(default=True, db_index=True)` | borrado lógico |

`Meta` declara `ordering = ["nombre"]`,
`UniqueConstraint(Lower("nombre"), name="uniq_espacio_nombre_ci")` y
`CheckConstraint(check=Q(capacidad__gt=0), name="ck_espacio_capacidad_positiva")`.

- **Motivo**: el nombre y la capacidad son invariantes del dominio; la restricción
  funcional y el `CHECK` los protegen incluso ante escrituras por ORM, `seed_data` o
  una futura importación.
- **Normalización del nombre**: el modelo recorta espacios al inicio y al final y
  colapsa espacios internos múltiples en `save()`; el formulario hace lo mismo en
  `clean_nombre`. Así `" Auditorio  Principal "` y `"auditorio principal"` no generan
  dos registros.
- **Alternativa descartada**: `unique=True` simple. La unicidad sería sensible a
  mayúsculas y permitiría duplicados semánticos.
- **Alternativa descartada**: validar solo en el formulario. `seed_data` y el ORM
  podrían crear duplicados.
- **Limitación conocida**: la unicidad no es insensible a acentos ni a signos
  (`"Auditorio"` vs `"Audítorio"` se consideran distintos). No lo exige el requisito
  y se documenta para no prometer más de lo que hace.

`EspacioQuerySet` propio con `activos()` e `inactivos()`, expuesto como
`objects = EspacioQuerySet.as_manager()`.

- **Motivo**: centraliza la noción de espacio disponible para el catálogo y para las
  futuras consultas de reservas, sin condicionar el manager por defecto (el
  administrador necesita ver todo).

Las reglas que no dependen del formato de la petición —normalizar el nombre,
detectar duplicados sin distinguir mayúsculas y validar la capacidad— se concentran
en `spaces/services.py` (`crear_espacio`, `actualizar_espacio`, `desactivar_espacio`
y `normalizar_nombre`). El modelo conserva sus restricciones como última defensa y
las vistas se limitan a invocar el servicio y elegir la respuesta, conforme a
REQ-BAS-007.

- **Motivo**: el formulario y `seed_data` comparten las mismas validaciones y las
  pruebas pueden ejercerlas sin cliente HTTP.
- **Alternativa descartada**: dejar toda la regla en `clean_nombre` del formulario.
  `seed_data` y el ORM podrían saltársela, y la vista quedaría acoplada a la
  validación.

### 2. `TipoEspacio` como `TextChoices` en `spaces/choices.py`

```text
class TipoEspacio(models.TextChoices):
    LABORATORIO = "LABORATORIO", "Laboratorio"
    AUDITORIO = "AUDITORIO", "Auditorio"
    SALA_COMPUTO = "SALA_COMPUTO", "Sala de cómputo"
```

- **Motivo**: el requisito fija exactamente tres valores; no hay CRUD de tipos ni
  atributos por tipo. Un `TextChoices` evita una tabla y un join, y coincide con la
  decisión de rol como campo tomada en `accounts`.
- **Alternativa descartada**: modelo `TipoEspacio` como sugiere el plan 2.4. Permite
  tipos dinámicos que el requisito no pide y complica la validación del filtro.
- **Alternativa descartada**: constantes sueltas. Pierden etiquetas legibles y la
  validación automática del formulario.

### 3. Desactivación lógica como única transición de estado

No se registra `DeleteView`, no hay ruta `.../eliminar/` ni acción de borrado en
plantillas. La única operación es `POST /espacios/<pk>/desactivar/`, que fija
`activo = False` y redirige con mensaje de éxito. Si el espacio ya está inactivo, la
operación es idempotente y solo informa.

- **Motivo**: REQ-ESP-006 exige conservar el registro para el historial de reservas;
  una eliminación física rompería futuras claves foráneas de `Reserva`.
- **Alternativa descartada**: `activo` editable en el formulario de edición. Mezcla
  la edición de datos con una transición de estado y permitiría reactivar sin una
  regla explícita; la reactivación está fuera de alcance.
- **Trade-off**: un espacio desactivado por error solo puede recuperarse por consola
  o con un futuro cambio que agregue reactivación. Se acepta para mantener el alcance
  y se anota como candidato a un cambio posterior.

### 4. Permisos reutilizados desde `accounts`

- `EspacioListView` y `EspacioDetailView` usan `LoginRequiredMixin`: cualquier
  autenticado consulta; anónimo redirige al login con `next`.
- `EspacioCreateView`, `EspacioUpdateView` y `EspacioDesactivarView` usan
  `RolRequeridoMixin` con `roles_permitidos = [Rol.ADMINISTRADOR]`: anónimo redirige
  al login y autenticado sin rol recibe 403.

- **Motivo**: cumple REQ-ESP-005 sin duplicar la comprobación y valida en uso real la
  reutilización que prometió REQ-USR-009.
- **Alternativa descartada**: `@login_required` más comprobaciones manuales de rol.
  Repetiría lógica y abriría la puerta a olvidos en futuras vistas.

### 5. Catálogo y filtro por tipo

`EspacioListView` construye el queryset así:

1. Si `user.rol == ADMINISTRADOR` → todos los espacios; si no → `objects.activos()`.
2. Si el parámetro `tipo` está presente y es un valor válido de `TipoEspacio` →
   filtra por ese tipo. Un valor inválido se ignora (se muestra el catálogo sin
   filtro) y se informa en la interfaz.
3. Orden por nombre.

El contexto incluye `tipos` para el selector, `tipo_seleccionado` y
`puede_administrar`. La plantilla muestra insignia de estado solo cuando el usuario
es administrador.

- **Motivo**: el filtro es de solo lectura y no amerita un formulario Django; el
  parámetro GET permite enlaces compartibles y pruebas directas.
- **Alternativa descartada**: filtrar en JavaScript. Impide verificar el escenario
  con el cliente de pruebas y depende de JS.
- **Alternativa descartada**: devolver 400 ante un tipo inválido. Añade una pantalla
  de error para un caso de uso menor; se prefiere degradar a "sin filtro".

### 6. Detalle con visibilidad condicionada

`EspacioDetailView.get_queryset()` devuelve todos los espacios para el
`ADMINISTRADOR` y solo activos para el resto. Un espacio inactivo solicitado por un
no administrador produce 404, no 403, para no revelar la existencia del registro.

- **Motivo**: REQ-ESP-008 limita el detalle inactivo al administrador; 404 evita
  filtrar información.
- **Alternativa descartada**: 403. Confirma que el recurso existe y mezcla
  autorización con visibilidad del catálogo.

### 7. Formulario único para crear y editar

`EspacioForm(ModelForm)` expone `nombre`, `tipo`, `capacidad`, `ubicacion` y
`descripcion` con widgets Bootstrap. Reglas:

- `clean_nombre`: normaliza espacios, valida duplicado sin distinguir mayúsculas
  excluyendo la instancia actual y devuelve un mensaje claro.
- `clean_capacidad`: rechaza valores menores que 1.
- `tipo`: las `choices` del modelo rechazan valores inválidos automáticamente.

- **Motivo**: un solo formulario evita divergencias entre creación y edición, y los
  mensajes en español se controlan en el formulario aunque la base de datos mantenga
  la última palabra.
- **Alternativa descartada**: formularios separados. Duplican validaciones sin
  diferencias reales de campos.

### 8. Rutas y plantillas

| Ruta | Nombre | Vista | Acceso |
|---|---|---|---|
| `espacios/` | `spaces:espacio_lista` | `EspacioListView` | autenticado |
| `espacios/<int:pk>/` | `spaces:espacio_detalle` | `EspacioDetailView` | autenticado (activos) |
| `espacios/crear/` | `spaces:espacio_crear` | `EspacioCreateView` | `ADMINISTRADOR` |
| `espacios/<int:pk>/editar/` | `spaces:espacio_editar` | `EspacioUpdateView` | `ADMINISTRADOR` |
| `espacios/<int:pk>/desactivar/` | `spaces:espacio_desactivar` | `EspacioDesactivarView` | `ADMINISTRADOR`, POST |

`spaces/urls.py` se incluye en `config/urls.py` bajo `espacios/`. Plantillas:
`espacio_lista.html`, `espacio_detalle.html`, `espacio_form.html` y
`espacio_confirmar_desactivar.html` (confirmación antes del POST).

`templates/base.html` reemplaza el enlace textual de espacios por
`{% url 'spaces:espacio_lista' %}`, visible para usuarios autenticados.

- **Motivo**: nombres de ruta estables que `reservations` reutilizará; confirmación
  explícita para una acción de estado.
- **Alternativa descartada**: desactivar desde un botón sin confirmación. Un clic
  accidental oculta el espacio del catálogo y no hay reactivación en este alcance.

### 9. `seed_data` con un espacio por tipo

Se agrega `sembrar_espacios()` al comando existente, con `get_or_create` sobre el
nombre exacto y sin sobrescribir registros existentes:

| Nombre | Tipo | Capacidad | Ubicación |
|---|---|---|---|
| `Laboratorio de Química` | `LABORATORIO` | 30 | Bloque B, piso 2 |
| `Auditorio Principal` | `AUDITORIO` | 200 | Bloque A, piso 1 |
| `Sala de Cómputo 1` | `SALA_COMPUTO` | 40 | Bloque C, piso 3 |

- **Motivo**: el plan 3.3 prevé espacios de ejemplo y el catálogo debe verse poblado
  en la demostración; `get_or_create` conserva la idempotencia de REQ-BAS-008.
- **Alternativa descartada**: fixtures con `pk` fijos. Chocan con datos existentes y
  no son idempotentes.
- **Trade-off**: si el administrador desactiva un espacio sembrado, una nueva
  ejecución no lo reactiva (no sobrescribe). Es coherente con la decisión 3 y con el
  respeto a los cambios hechos desde la interfaz.

### 10. Pruebas por escenario

`spaces/tests/`:

- `utils.py`: helper `crear_espacio(nombre=..., tipo=..., capacidad=..., activo=True)`.
- `test_models.py`: campos, estado activo por defecto, unicidad insensible a
  mayúsculas, capacidad positiva, queryset `activos()`.
- `test_forms.py`: tipo inválido, capacidad 0/negativa/decimal, duplicado al crear y
  al renombrar, creación válida.
- `spaces/tests/test_views.py`: catálogo, filtro, visibilidad de inactivos según rol, detalle,
  404 de inactivo para solicitante, 404 de inexistente, redirección de anónimos, 403
  de solicitante y aprobador, creación/edición/desactivación por administrador,
  inexistencia de ruta de borrado y persistencia del registro desactivado.
- `spaces/tests/test_seed_data.py`: se crea en la suite de `spaces` para comprobar un
  espacio por tipo y que dos ejecuciones no duplican registros; la prueba de
  `seed_data` de `core` conserva solo las comprobaciones de usuarios.

Se conserva `spaces/tests/test_permissions.py` creado por
`usuarios-roles-permisos`; si el archivo ya existe, este cambio no lo reescribe.

- **Motivo**: el plan 5.3 exige una prueba por escenario con el identificador del
  requisito; separar modelo, formulario y vistas aísla la causa de cada fallo.
- **Alternativa descartada**: una única prueba de extremo a extremo. No distingue si
  falla la restricción de base, el formulario o el permiso.

## Risks / Trade-offs

- **Dependencia de cambios previos** → este cambio se implementa después de
  `base-proyecto` y `usuarios-roles-permisos`; sin ellos no existen roles ni el
  mecanismo de permisos. Se registra como precondición en `tasks.md`.
- **Índice funcional `Lower(nombre)` en SQLite** → soportado en las versiones que
  acompañan a Python 3.12; se verifica con `migrate` en base limpia y con la prueba
  de duplicados. Si fallara, la alternativa es normalizar a minúsculas en `save()` y
  usar `unique=True`.
- **Carrera al crear dos espacios con el mismo nombre** → la restricción de base de
  datos es la garantía final; el formulario evita el error genérico en el caso
  normal. Si la restricción salta, se traduce a un error de formulario.
- **Sin reactivación** → un espacio desactivado por error requiere consola; se
  documenta como deuda consciente y candidato a cambio posterior.
- **Normalización de espacios internos** → `save()` altera el nombre recibido; se
  documenta para que `seed_data` y las pruebas usen el nombre normalizado.
- **Colisión con el archivo de pruebas de permisos de `accounts`** → se conserva el
  archivo existente y se agregan pruebas nuevas en archivos separados.
- **Futuras claves foráneas de reservas** → `Reserva` deberá usar
  `on_delete=PROTECT` hacia el espacio y filtrar por `activo` al crear solicitudes;
  se anota para el cambio de `reservas`.

## Migration Plan

1. Confirmar que `base-proyecto` y `usuarios-roles-permisos` están implementados y
   con la suite en verde.
2. Crear `spaces/choices.py` y `spaces/models.py` con `EspacioAcademico`, su manager y
   sus restricciones.
3. Generar `spaces/migrations/0001_initial.py` y aplicar `migrate`; verificar la
   tabla, el índice de unicidad y el `CHECK` de capacidad.
4. Implementar `spaces/services.py`, `spaces/forms.py`, `spaces/views.py`,
   `spaces/urls.py` y las plantillas; incluir las rutas en `config/urls.py` y
   actualizar el enlace de `base.html`.
5. Ampliar `seed_data` con los tres espacios y crear
   `spaces/tests/test_seed_data.py`; conservar en `core` solo las comprobaciones de
   usuarios.
6. Escribir la suite `spaces/tests/` y ejecutar `python manage.py test` completa.

**Rollback**: revertir el commit y eliminar la migración de `spaces` junto con la
tabla creada. Como el cambio no modifica datos de usuarios ni de otros módulos y aún
no existen reservas, no hay pérdida de información; si ya se ejecutó `seed_data`, los
espacios sembrados desaparecen con la tabla.

## Open Questions

Ninguna que afecte las especificaciones, el enfoque o el desglose de tareas. La
posible reactivación de espacios queda explícitamente fuera de alcance y no altera
los requisitos actuales.
