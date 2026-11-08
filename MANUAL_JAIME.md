# Manual de usuario — Bosselli Gestión

Aplicación privada de gestión para las dos tiendas Bosselli (Nervión y Porvenir).
No es una tienda online ni un TPV de cobro: registra y archiva las ventas, compras,
gastos, nóminas y facturas para que la gestión y la declaración a la gestoría
sean sencillas.

---

## 1. Acceso

- URL: la que te indique el administrador (en local: http://127.0.0.1:8000/).
- Usuario: `jaime` · Contraseña: `bosselli2024` (cámbiala en "Mi perfil").
- El icono del ojo en el campo de contraseña permite verla mientras la escribes.
- El administrador (superusuario) tiene además un enlace "Panel de administración"
  que abre Django Admin en una pestaña nueva.

## 2. Panel (dashboard)

Resumen del mes: ventas, beneficio estimado, gastos, ticket medio, gráfico de los
últimos 6 meses, stock bajo, últimas ventas y tareas pendientes (facturas por
revisar, compras pendientes de pago, nóminas en borrador).

## 3. Artículos y stock

- **Artículos**: catálogo de prendas (camisas, trajes, chaqués, cazadoras,
  jerseys, corbatas, pañuelos, complementos). Cada artículo tiene referencia,
  familia, proveedor, coste, PVP, IVA, stock mínimo y foto.
- **Variantes**: tallas y colores de cada artículo. Desde la ficha del artículo
  se añaden.
- **Stock**: unidades por variante y por tienda. Ajustes manuales (entradas,
  salidas, devoluciones) y **traspasos** entre Nervión y Porvenir.
- Alertas automáticas cuando el stock está por debajo del mínimo.

## 4. Ventas

Registrar una venta (ticket, factura o resumen de la web): fecha, tienda,
cliente, forma de pago, estado. Se pueden añadir líneas con artículo, variante,
cantidad, precio y descuento. Si se marca "Descontar stock", se descuenta
automáticamente. Genera PDF y se puede enviar por email al cliente.

## 5. Compras

Facturas de proveedores: número, fecha, proveedor, importe. Al marcar
"Recibida", la mercancía entra en stock y se actualiza el coste del artículo.
Estados: pendiente de pago / pagada / anulada.

## 6. Gastos

Gastos por categoría (alquiler, suministros, seguros, servicios, publicidad,
transporte, personal, impuestos, mantenimiento, compras, otros). Se pueden
vincular a una tienda y marcar como recurrentes.

## 7. Clientes y proveedores

Fichas con datos de contacto. Los proveedores se crean automáticamente al
importar una factura si no existen.

## 8. Empleados y nóminas

Fichas de empleados (NIF, NSS, puesto, tienda, salario anual). Nóminas
mensuales con salario base, IRPF, Seguridad Social y neto. Genera recibo en PDF.

## 9. Facturas (lectura automática)

Tres vías disponibles:

1. **PDF digital**: sube el PDF y el sistema extrae proveedor, CIF, fecha,
   base, IVA y total.
2. **Foto de factura**: si el servidor tiene OCR instalado, intenta leer la foto.
3. **Rellenar a mano**: siempre disponible en la pantalla de revisión.

Flujo: Subir factura → Revisar datos detectados → Crear gasto / compra / venta
pre-rellenado. El archivo original se vincula automáticamente y la factura
queda marcada como "Revisada".

## 10. Informes

Listados en PDF y Excel: ventas, compras, gastos, artículos, stock, clientes,
proveedores, empleados, nóminas. Filtrables por fecha y tienda.

## 11. Gestoría

Genera un **ZIP** con:
- Resumen del trimestre en Excel (ventas, compras, gastos, nóminas, resultado).
- Resumen en PDF.
- Todas las facturas adjuntas a cada venta, compra y gasto.

Se puede descargar o enviar por email a la gestoría con un clic.

## 12. Auditoría

Todo lo que se hace queda registrado: quién, cuándo, qué cambió. Visible en
"Historial" (solo para gestores y administradores).

## 13. PWA (instalar en el móvil)

La aplicación se puede instalar en el móvil como una app (icono en la pantalla
de inicio) para acceso rápido. Funciona offline para los estáticos.

---

Bosselli · Sastrería y moda clásica desde 1973. Documento interno de gestión.