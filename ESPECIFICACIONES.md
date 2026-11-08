# Especificaciones – Proyecto Django multi-tenant (plantilla base)

Documento reutilizable: **cada proyecto nuevo debe partir de estas especificaciones.**
Vertical inicial: gestión de taller mecánico. Después: administradores de fincas (reutilizando `core`).


---

## 1. Objetivo
SaaS multi-tenant para vender a varios clientes (talleres y, más adelante, administradores de fincas) con una base común (`core`) y una app por vertical.

## 2. Requisitos obligatorios en todo proyecto nuevo
Estos puntos NO son opcionales:

1. **WhiteNoise** para servir estáticos (sección 4).
2. **Live reload solo con `DEBUG=True`** (sección 5).
3. **Modelo de auditoría** que registre todo lo que se hace en la aplicación (sección 6).
4. **Multi-tenant** con aislamiento por organización y tests (sección 7).
5. **UI mobile-first + PWA** (sección 13).

## 3. Stack
- Python 3.11+ (probado con 3.13)
- Django >=5.2,<7
- UI móvil/tablet primero: Bootswatch + SweetAlert2 + toasts + AJAX (fetch + CSRF)
- Static files: **WhiteNoise** (despliegue en PythonAnywhere)
- Live reload: **django-browser-reload** (solo en desarrollo)
- DB desarrollo: SQLite
- DB producción: PostgreSQL o SQL Server (configuración preparada y comentada)
- Otras dependencias: `pywebpush`, `python-dotenv`/`environ`, `dj-database-url`, `Pillow`

## 4. WhiteNoise (obligatorio)
- Instalar: `pip install whitenoise`.
- En `settings.py`, justo después de `SecurityMiddleware`:
  ```python
  MIDDLEWARE = [
      "django.middleware.security.SecurityMiddleware",
      "whitenoise.middleware.WhiteNoiseMiddleware",
      # ... resto
  ]
  STATIC_URL = "/static/"
  STATIC_ROOT = BASE_DIR / "staticfiles"
  STATICFILES_DIRS = [BASE_DIR / "static"]
  STORAGES = {
      "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
      "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
  }
  ```
- Ejecutar `python manage.py collectstatic --noinput` antes de cada despliegue.
- `media/` (fotos, firmas) no lo sirve WhiteNoise: en PythonAnywhere se configura como *Static files mapping*.

## 5. Live reload solo en modo debug (obligatorio)
- Instalar: `pip install django-browser-reload` (va en `requirements-dev.txt`, no en producción).
- Se activa **únicamente** si `DEBUG=True`:
  ```python
  # settings.py
  if DEBUG:
      INSTALLED_APPS += ["django_browser_reload"]
      MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]
  ```
  ```python
  # urls.py
  from django.conf import settings
  if settings.DEBUG:
      urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]
  ```
- Con `DJANGO_DEBUG=0` no se carga la app, ni el middleware, ni la URL.
- El import debe estar protegido para que producción arranque aunque el paquete no esté instalado.

## 6. Modelo de auditoría (obligatorio)
Registro de **todo lo que se hace** en la aplicación: quién, cuándo, dónde y qué cambió.

### 6.1 Modelo `Auditoria` (en `core`, hereda de `TenantModel`)
| Campo | Descripción |
|---|---|
| `organizacion` | FK a `Organizacion` (null en acciones globales) |
| `usuario` | FK a `User` (null si es el sistema) |
| `usuario_nombre` | copia del username (se conserva si se borra el usuario) |
| `fecha` | `DateTimeField(auto_now_add=True, db_index=True)` |
| `accion` | `crear`, `editar`, `borrar`, `login`, `logout`, `login_fallido`, `exportar`, `cambio_estado`, `firma`, `envio_aviso`, `otro` |
| `content_type` + `object_id` | objeto afectado (GenericForeignKey) |
| `objeto_repr` | `str()` del objeto en ese momento |
| `cambios` | `JSONField` con `{campo: [antes, despues]}` |
| `ip` | IP del cliente (respetando `X-Forwarded-For` en PythonAnywhere) |
| `user_agent` | navegador/dispositivo |
| `ruta` / `metodo` | URL y método HTTP de la petición |

### 6.2 Qué se audita
- Altas, ediciones y borrados de **todos** los modelos de negocio (Cliente, Vehículo, Orden, Línea, Pieza, Perfil, etc.) mediante señales `post_save`, `pre_save` (para calcular el diff) y `post_delete`.
- Login, logout y login fallido (`user_logged_in`, `user_logged_out`, `user_login_failed`).
- Acciones AJAX: cambio de estado, firma, subida de fotos, avisos por email/WhatsApp/push.
- Exportaciones a Excel/PDF.
- Cambios hechos desde el panel de administración.
- Cambios de rol y de contraseña (sin guardar nunca la contraseña ni su hash en `cambios`).

### 6.3 Implementación
- **Middleware** `AuditoriaMiddleware`: guarda `request.user`, IP, user-agent, ruta y método en un almacén thread-local/contextvar para que las señales sepan quién actúa.
- **Señales** registradas automáticamente para todos los modelos que hereden de `TenantModel` (excluyendo `Auditoria` para evitar recursión).
- **Campos excluidos** configurables: `password`, tokens, claves VAPID, imágenes en base64 de firmas (se registra solo "firma actualizada").
- **Inmutable**: en el admin `Auditoria` es solo lectura (sin añadir, editar ni borrar), filtrable por usuario, acción, modelo y fecha, con búsqueda por objeto.
- Cada registro se filtra por organización: un taller solo ve su propia auditoría; el superusuario ve todo.
- Retención: conservar al menos 12 meses; comando de gestión `purgar_auditoria --meses N` opcional.
- Vista "Historial de actividad" en la app (solo rol `admin`) y botón "Historial" en el detalle de cada orden/cliente/vehículo.
- Tests: crear/editar/borrar generan registro; el diff es correcto; no se guardan contraseñas; aislamiento entre organizaciones.

### 6.4 RGPD
La auditoría contiene datos personales (usuario, IP): documentarla en la política de privacidad y en el contrato de encargado de tratamiento.

## 7. Multi-tenant
- Modelo `Organizacion` (cada cliente).
- `Perfil` vincula `User` → `Organizacion` y define el `rol`.
- `TenantModel` abstracto con FK a `organizacion` y manager que filtra por organización.
- Middleware que asigna `request.organizacion`.
- Regla: toda consulta filtra por organización. Tests de aislamiento.

## 8. Estructura
```
core/        # Organizacion, Perfil, TenantModel, Auditoria, middleware, admin base, gestión
taller/      # Cliente, Vehiculo, Orden, Linea, Pieza, Firma, FotoOrden
fincas/      # Comunidad, Inmueble, Recibo, Derrama, Incidencia, FirmaDocumento
templates/   # base.html + vistas
static/      # css/js (app.js con toast, confirmar, api), manifests, sw.js
media/       # fotos de entrada y firmas (ImageField)
```

## 9. Modelos clave (taller)
- `Cliente`: nombre, teléfono, email, notas.
- `Vehiculo`: matrícula, bastidor, km, ITV, cliente (FK).
- `Orden`: número por taller, estado (recibido, presupuestado, aprobado, en curso, listo, entregado), vehículo, fechas, observaciones.
- `Linea`: orden (FK), tipo (mano de obra/recambio), descripción, cantidad, precio, pieza opcional.
- `Pieza`: código, nombre, proveedor, coste, venta, stock, mínimo.
- `Firma`: PNG uno a uno con la orden.
- `PushSubscription`: una fila por dispositivo suscrito.

## 10. Funcionalidad MVP
1. Alta rápida cliente + vehículo por matrícula.
2. CRUD completo de Cliente, Vehículo, Orden, Línea y Pieza.
3. Órdenes con cambio de estado vía AJAX.
4. Líneas AJAX con confirmación al borrar.
5. Buscador de matrícula e historial por vehículo.
6. Dashboard: coches por estado + ITV próximas + stock bajo + control de dinero.
7. Admin filtrado por taller.
8. Listados con paginación, búsqueda AJAX en tiempo real y selector de tamaño de página (mín. 5).
9. Orden de listados: más reciente primero.
10. Auditoría de todas las acciones (sección 6).

## 11. Funcionalidades adicionales

### 11.1 Control de dinero
- Dashboard con ingresos totales, ingresos del mes, ticket medio y top clientes.
- Ingresos calculados a partir de órdenes cerradas (listo/entregado).

### 11.2 Exportaciones y comunicación
- Exportar listados a Excel y PDF (clientes, vehículos, órdenes).
- Aviso al cliente por email (Gmail) y enlace de WhatsApp (`wa.me`).
- Fotos de entrada por orden (captura desde móvil con `capture`).
- Presupuesto/orden en PDF.
- Recordatorios ITV/aceite (posterior).

### 11.3 Catálogo de piezas y stock
- Líneas de recambio pueden vincular una pieza del catálogo.
- Descuento automático de stock al entregar la orden.
- Alerta en dashboard de piezas con stock bajo.

### 11.4 Datos de prueba
- Script `seed.py` para poblar la BD con datos ficticios (clientes, vehículos, órdenes, líneas).

## 12. Acceso, usuarios y roles
- Login con campo de contraseña y botón "ojo" para mostrar/ocultar.
- Superusuario: enlace al panel admin en nueva pestaña desde el menú.
- Creación de usuarios con contraseña y toggle de visibilidad.
- Manual de usuario para Borja (`MANUAL_BORJA.md`) con credenciales y uso.
- Campo `rol` en `Perfil`: `admin`, `mecanico`, `recepcion`.
- Los borrados de clientes, vehículos, órdenes y piezas exigen rol `admin` (el superusuario siempre puede).
- El rol se cambia desde el panel de administración (Core → Perfiles). Todo cambio de rol queda auditado.

## 13. PWA y experiencia móvil
- Dos manifests: taller (`/`) y fincas (`/fincas/`), con iconos 192 y 512.
- Service worker servido desde `/sw.js` (raíz) con `Service-Worker-Allowed: /`: red primero para páginas y caché para estáticos; la app sigue abriendo si falla la conexión.
- Diseño mobile-first: menú colapsable, botones de al menos 40 px, tablas con scroll horizontal (`table-responsive`), formularios a una columna y canvases de firma adaptados al ancho con coordenadas corregidas por escala.
- `viewport-fit=cover` y `theme-color` para la barra del navegador/PWA.

## 14. Firma digital
- **Taller**: canvas táctil en el detalle de la orden (ratón o dedo). Se guarda como PNG (`Firma`, uno a uno con la orden) y se incrusta en el PDF; si no hay firma se imprime la línea para firmar a mano.
- **Fincas**: cada documento de la comunidad se puede firmar desde el portal del vecino. Se guarda en `FirmaDocumento` (PNG) y se muestra junto al documento.
- Cada firma queda registrada en la auditoría.

## 15. Notificaciones push (Web Push)
- Botón en la barra superior **Activar avisos**: la primera vez pide permiso y registra la suscripción; las siguientes envía un aviso de prueba.
- Avisos automáticos:
  - Vehículo marcado como **listo** → al resto de usuarios de la organización.
  - Nueva incidencia desde el portal del vecino → a los gestores (excepto quien la crea).
- Endpoints: `/api/push/clave/`, `/api/push/suscribir/`, `/api/push/baja/`, `/api/push/probar/`.
- Claves VAPID en `.env`; la privada va en base64url DER, no PEM.
- Requiere HTTPS en producción (PythonAnywhere lo incluye). En iOS 16.4+ hay que instalar la web en la pantalla de inicio.
- Dependencia: `pywebpush`.

## 16. Fincas (segunda vertical)
- Lista de comunidades con concepto e importe total de la cuota.
- El importe se reparte entre los inmuebles según su coeficiente, redondeado a 2 decimales.
- Recibos y derramas con `fecha_vencimiento` editable.
- Botón para generar los recibos de una derrama existente.
- Portal del vecino: documentos, firma e incidencias.

## 17. Legal
- No emitir facturas desde la app al inicio (Verifactu). Exportar datos al gestor del taller.
- RGPD: contrato de encargado de tratamiento + política de privacidad (incluye auditoría, IP y notificaciones push).

## 18. Variables de entorno (`.env`)
```
DJANGO_DEBUG=1                    # 1 = desarrollo (activa live reload); 0 = producción
DJANGO_SECRET_KEY=...
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=                     # vacío = SQLite
# PostgreSQL:
# DATABASE_URL=postgres://user:pass@host:5432/dbname
# SQL Server:
# DATABASE_URL=mssql://user:pass@host/dbname?driver=ODBC+Driver+17+for+SQL+Server
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=tu@gmail.com
EMAIL_HOST_PASSWORD=app_password
DEFAULT_FROM_EMAIL=tu@gmail.com
VAPID_PUBLIC_KEY=...              # clave pública Web Push (base64url)
VAPID_PRIVATE_KEY=...             # clave privada Web Push (base64url DER)
VAPID_ADMIN_EMAIL=tu@gmail.com
AUDITORIA_RETENCION_MESES=12
```

## 19. Despliegue (PythonAnywhere)
- `DEBUG=0` en producción (live reload desactivado automáticamente).
- WhiteNoise para estáticos; `collectstatic` antes de desplegar.
- `ALLOWED_HOSTS` con el dominio de PythonAnywhere.
- Mapeo de `/media/` en la pestaña *Web → Static files*.
- Instalar solo `requirements.txt` (sin las dependencias de desarrollo).

## 20. Comandos base
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # solo en desarrollo (django-browser-reload)
python manage.py migrate
python manage.py createsuperuser
python manage.py crear_taller "Taller Borja" borja --password "UnaClaveSegura1"
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8000
```

## 21. Checklist al crear un proyecto nuevo
- [ ] Entorno virtual + `requirements.txt` y `requirements-dev.txt`
- [ ] `core` con `Organizacion`, `Perfil`, `TenantModel` y middleware de organización
- [ ] WhiteNoise configurado y `collectstatic` probado
- [ ] Live reload cargado solo con `DEBUG=True`
- [ ] Modelo `Auditoria` + middleware + señales + admin de solo lectura
- [ ] Tests de aislamiento entre organizaciones y de auditoría
- [ ] `.env` con todas las variables (incluida `DJANGO_DEBUG`)
- [ ] PWA (manifest, `/sw.js`, iconos) y diseño mobile-first
- [ ] `seed.py` y manual de usuario
