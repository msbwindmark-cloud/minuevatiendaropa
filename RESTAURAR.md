# Guía de restauración — Bosselli Gestión

Documento con los pasos detallados para restaurar la base de datos y los archivos
desde un backup. Guarda este archivo junto con tus backups.

---

## Índice

1. [Restaurar desde backup ZIP (recomendado)](#1-restaurar-desde-backup-zip)
2. [Restaurar copiando el SQLite directamente](#2-restaurar-copiando-el-sqlite-directamente)
3. [Restaurar en PythonAnywhere](#3-restaurar-en-pythonanywhere)
4. [Restaurar solo una tabla](#4-restaurar-solo-una-tabla)
5. [Solución de problemas](#5-solucion-de-problemas)
6. [Checklist de verificación](#6-checklist-de-verificacion)

---

## 1. Restaurar desde backup ZIP

### 1.1. Requisitos previos

- Python 3.11+ instalado
- Git (opcional, si clonas el repositorio)
- El archivo ZIP de backup (ej: `backup_bosselli_20261108_1256.zip`)
- La carpeta `media/` del servidor (facturas, imágenes de artículos)

### 1.2. Instalar el proyecto

```bash
# Clonar o copiar el proyecto
git clone <url-del-repo> minuevatiendaropa
cd minuevatiendaropa

# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 1.3. Configurar el entorno

Copia `.env.example` a `.env` y edita los valores:

```bash
cp .env.example .env
```

Edita `.env`:
```
DJANGO_DEBUG=True
DJANGO_SECRET_KEY=tu-clave-secreta-aqui
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=tuemail@gmail.com
EMAIL_HOST_PASSWORD=tu-app-password
DEFAULT_FROM_EMAIL=Bosselli <tuemail@gmail.com>
```

### 1.4. Crear la base de datos vacía

```bash
python manage.py migrate
```

Esto crea todas las tablas vacías en `db.sqlite3`.

### 1.5. Descomprimir el backup

```bash
# Windows (PowerShell):
Expand-Archive -Path backup_bosselli_20261108_1256.zip -DestinationPath backup_temp

# Linux/Mac:
unzip backup_bosselli_20261108_1256.zip -d backup_temp
```

### 1.6. Cargar los datos

**Opción A: Cargar todo de una vez (recomendado)**

```bash
python manage.py loaddata backup_temp/json/backup_completo.json
```

**Opción B: Cargar tabla por tabla (si hay errores)**

Carga en este orden (respetando las dependencias):

```bash
python manage.py loaddata backup_temp/json/organizacion.json
python manage.py loaddata backup_temp/json/tienda.json
python manage.py loaddata backup_temp/json/familia.json
python manage.py loaddata backup_temp/json/proveedor.json
python manage.py loaddata backup_temp/json/cliente.json
python manage.py loaddata backup_temp/json/articulo.json
python manage.py loaddata backup_temp/json/variante.json
python manage.py loaddata backup_temp/json/stock.json
python manage.py loaddata backup_temp/json/venta.json
python manage.py loaddata backup_temp/json/lineaventa.json
python manage.py loaddata backup_temp/json/compra.json
python manage.py loaddata backup_temp/json/lineacompra.json
python manage.py loaddata backup_temp/json/gasto.json
python manage.py loaddata backup_temp/json/empleado.json
python manage.py loaddata backup_temp/json/nomina.json
python manage.py loaddata backup_temp/json/facturaimportada.json
```

### 1.7. Copiar los archivos media

```bash
# Copiar la carpeta media del backup (o del servidor original)
# Windows:
xcopy /E /I backup_temp\media media

# Linux/Mac:
cp -r backup_temp/media/* media/
```

Si no tienes la carpeta `media/` del backup, copia la del servidor original:
```
/home/<usuario>/minuevatiendaropa/media/ → media/
```

### 1.8. Crear superusuario

El backup NO incluye el superusuario (por seguridad). Créalo:

```bash
python manage.py createsuperuser
```

Introduce:
- Username: `daw2`
- Email: tu email
- Password: una contraseña segura

### 1.9. Verificar y arrancar

```bash
python manage.py check
python manage.py runserver
```

Abre http://127.0.0.1:8000/ y entra con el usuario creado.

---

## 2. Restaurar copiando el SQLite directamente

Si tienes acceso al archivo `db.sqlite3` del servidor:

### 2.1. Pasos

1. Instala el proyecto (pasos 1.2 y 1.3).
2. **NO ejecutes** `python manage.py migrate`.
3. Copia el archivo `db.sqlite3` del servidor a la raíz del proyecto.
4. Copia la carpeta `media/` del servidor.
5. Ejecuta migraciones por si hay cambios:
   ```bash
   python manage.py migrate
   ```
6. Crea el superusuario si no existe:
   ```bash
   python manage.py createsuperuser
   ```
7. Arranca:
   ```bash
   python manage.py runserver
   ```

### 2.2. Cuándo usar esta opción

- Cuando tienes acceso directo al servidor (PythonAnywhere, local).
- Cuando quieres una restauración exacta (incluye usuarios, sesiones, etc.).
- Cuando el backup ZIP falla por algún motivo.

### 2.3. Cuándo NO usar esta opción

- Si la versión de Django es diferente (puede haber incompatibilidades de esquema).
- Si quieres limpiar datos corruptos (mejor empezar de cero con el JSON).

---

## 3. Restaurar en PythonAnywhere

### 3.1. Subir archivos

1. Entra en PythonAnywhere → pestaña **Files**.
2. Navega a `/home/<tu_usuario>/minuevatiendaropa/`.
3. Sube `db.sqlite3` (o el ZIP descomprimido).
4. Sube la carpeta `media/` completa.

### 3.2. Desde la consola Bash de PA

```bash
cd /home/<tu_usuario>/minuevatiendaropa
# Si subiste el ZIP:
unzip backup_bosselli_YYYYMMDD_HHMM.zip -d .
# Si subiste db.sqlite3 directamente, ya está.

# Aplicar migraciones
python manage.py migrate

# Crear superusuario si es necesario
python manage.py createsuperuser

# Recoger estáticos
python manage.py collectstatic --noinput
```

### 3.3. Reiniciar la web app

1. Ve a la pestaña **Web**.
2. Pulsa **"Reload"** en tu web app.
3. Verifica que la app carga correctamente.

### 3.4. Verificar media

En la pestaña **Web**, sección **Static files**, verifica que exista:
- URL: `/media/` → Directorio: `/home/<tu_usuario>/minuevatiendaropa/media`

---

## 4. Restaurar solo una tabla

Si solo necesitas restaurar una tabla específica (ej: solo las ventas):

```bash
# Restaurar solo ventas
python manage.py loaddata backup_temp/json/venta.json

# Restaurar solo clientes
python manage.py loaddata backup_temp/json/cliente.json

# Restaurar solo artículos
python manage.py loaddata backup_temp/json/articulo.json
```

**Nota:** Si la tabla ya tiene datos, `loaddata` puede fallar por duplicados. En ese caso:
1. Borra los datos de esa tabla desde el admin o con:
   ```bash
   python manage.py shell
   >>> from negocio.models import Venta
   >>> Venta.all_objects.all().delete()
   ```
2. Carga de nuevo:
   ```bash
   python manage.py loaddata backup_temp/json/venta.json
   ```

---

## 5. Solución de problemas

### Error: "No such table"
**Causa:** No se ejecutaron las migraciones.
**Solución:**
```bash
python manage.py migrate
```

### Error: "IntegrityError: UNIQUE constraint failed"
**Causa:** Ya existen datos con los mismos IDs.
**Solución:** Borra los datos existentes antes de cargar:
```bash
python manage.py shell
>>> from negocio.models import Venta, Cliente, Articulo
>>> Venta.all_objects.all().delete()
>>> Cliente.all_objects.all().delete()
>>> Articulo.all_objects.all().delete()
```
Luego carga el backup.

### Error: "DeserializationError: Invalid model identifier"
**Causa:** La versión de Django es diferente.
**Solución:** Usa la misma versión de Django que generó el backup. Verifica con:
```bash
python -c "import django; print(django.VERSION)"
```

### Error: "FileNotFoundError: media/..."
**Causa:** Falta la carpeta `media/`.
**Solución:** Copia la carpeta `media/` del servidor original.

### Error: "Permission denied" en PythonAnywhere
**Causa:** Permisos de archivo.
**Solución:**
```bash
chmod 644 db.sqlite3
chmod -R 755 media/
```

### Las imágenes no se ven
**Causa:** La carpeta `media/` no está mapeada en PythonAnywhere.
**Solución:** En la pestaña Web → Static files, añade:
- URL: `/media/`
- Directorio: `/home/<tu_usuario>/minuevatiendaropa/media`

---

## 6. Checklist de verificación

Después de restaurar, verifica:

- [ ] La app carga sin errores (`python manage.py check`)
- [ ] El login funciona con los usuarios existentes
- [ ] Los artículos se ven con sus imágenes
- [ ] El stock es correcto
- [ ] Las ventas aparecen en el listado
- [ ] Los informes PDF/Excel se generan
- [ ] El paquete de gestoría se genera correctamente
- [ ] El backup se puede descargar
- [ ] Las notificaciones funcionan
- [ ] El panel de admin muestra todos los modelos

---

## Notas importantes

1. **Los archivos media (facturas, imágenes) NO están en el ZIP**. Debes copiarlos aparte desde la carpeta `media/` del servidor.

2. **El usuario superusuario NO se incluye** en el backup (por seguridad). Debes crearlo manualmente con `createsuperuser`.

3. **Las contraseñas de los usuarios** sí se incluyen en el backup (están encriptadas en el JSON). Después de restaurar, los usuarios pueden entrar con sus contraseñas originales.

4. **El backup es compatible** entre la misma versión de Django. Si actualizas Django, puede haber problemas de compatibilidad.

5. **Guarda siempre el ZIP y la carpeta media/ juntos**. Sin la carpeta media, las facturas y las imágenes de los artículos no se verán.

6. **Haz backup regularmente**. Se recomienda un backup diario (automático o manual) y un backup antes de cualquier actualización importante.

---

*Bosselli Gestión — Sastrería y moda clásica desde 1973*
*Documento de restauración — Guardar junto con los backups*