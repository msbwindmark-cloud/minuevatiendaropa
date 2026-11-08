# Especificaciones — Anexo Bosselli

Documento anexo a `ESPECIFICACIONES.md` (plantilla base reutilizable). Mantiene
intacta la base técnica y detalla la adaptación al negocio de Bosselli.

## 1. Organización y tiendas

- Una sola organización: **Bosselli** (CIF B41123456).
- Dos tiendas:
  - **Nervión** — Avda. San Francisco Javier 7, Sevilla. Código `NER`.
  - **Porvenir** — Avda. Ramón Carande 14, Sevilla. Código `POR`.
- Multi-tenant conservado: cada tienda tiene su propio stock; los movimientos
  y traspasos se registran por tienda.

## 2. Usuarios

- `daw2` — superusuario. Acceso a `/admin/` en pestaña nueva.
- `jaime` — administrador de la organización (rol `admin`).
- `vendedor` — vendedor (rol `vendedor`), acceso limitado.

Contraseña inicial de todos: `bosselli2024` (cambiar en producción).

## 3. Módulos

1. **Artículos** — catálogo de prendas (camisas, trajes, chaqués, cazadoras,
   jerseys, corbatas, pañuelos, complementos) con referencia, familia,
   proveedor, coste, PVP, IVA, stock mínimo, foto.
2. **Variantes** — tallas y colores por artículo.
3. **Stock** — unidades por variante y tienda; ajustes y traspasos; alertas
   de stock bajo; valoración a coste y PVP.
4. **Clientes** — fichas con historial de compras.
5. **Proveedores** — fichas; creación automática al importar facturas.
6. **Ventas** — registro de tickets, facturas y resúmenes de la web; líneas
   opcionales; descuento de stock; PDF y envío por email.
7. **Compras** — facturas de proveedores; entrada de mercancía y actualización
   de coste.
8. **Gastos** — por categoría; vinculables a tienda; recurrentes.
9. **Empleados** — fichas con NIF, NSS, puesto, tienda, salario anual.
10. **Nóminas** — mensuales con base, IRPF, SS empleado/empresa, neto; PDF.
11. **Facturas importadas** — subida de PDF/foto, extracción de datos (PDF
    con texto, OCR opcional, relleno manual), revisión y creación de
    gasto/compra/venta.
12. **Informes** — listados en PDF y Excel.
13. **Gestoría** — paquete trimestral ZIP (Excel + PDF + facturas adjuntas)
    y envío por email.
14. **Auditoría** — registro completo de acciones.

## 4. Lectura de facturas (3 vías)

- PDF digital → extracción de texto con `pypdf` y patrones.
- Foto (JPG/PNG/etc.) → OCR con Tesseract si está instalado (`OCR_ACTIVO`).
- Siempre manual: pantalla de revisión con formulario pre-rellenado.

## 5. Stack y despliegue

- Django 6.1.3, SQLite (dev), WhiteNoise, Bootstrap 5 + Bootswatch (self-hosted),
  reportlab (PDF), openpyxl (Excel), pypdf (PDF text), pytesseract (OCR opcional).
- PWA: manifest + service worker + iconos.
- Preparado para PythonAnywhere: `DJANGO_DEBUG=0`, guard `ON_PYTHONANYWHERE`,
  media mapping `/media/` → `/home/<usuario>/bosselli/media`.
- Live reload solo con `DEBUG=True`.

## 6. Datos demo

Comando `python manage.py seed` puebla la base con:
- 2 tiendas, 8 familias, 5 proveedores, 10 clientes.
- 44 artículos con variantes y stock en ambas tiendas.
- 4 empleados, 6 meses de gastos fijos y variables.
- 12 compras, 60 ventas, 6 meses de nóminas.

Basado en el catálogo real de https://www.bosselli.es (camisas, trajes,
chaqués, cazadoras, jerseys, corbatas, pañuelos, complementos).

## 7. Branding

- Navy `#0f172a`, oro `#b08d57`, crema `#f8f5ef`.
- Tipografía: Georgia para títulos, Segoe UI para cuerpo.
- Layout con sidebar (desktop) y offcanvas (móvil). Mobile-first.

## 8. Notas de producción

- Cambiar `DJANGO_SECRET_KEY` y `DJANGO_DEBUG=0`.
- Configurar `DJANGO_ALLOWED_HOSTS` con el dominio de PythonAnywhere.
- Mapear `/media/` → `/home/<usuario>/bosselli/media` en el panel de PA.
- Configurar SMTP para envío de emails.
- Instalar Tesseract en el sistema si se quiere OCR de fotos.