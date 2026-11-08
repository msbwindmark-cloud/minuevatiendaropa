from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    # Artículos y stock
    path("articulos/", views.articulos, name="articulos"),
    path("articulos/nuevo/", views.articulo_form, name="articulo_nuevo"),
    path("articulos/<int:pk>/", views.articulo_detalle, name="articulo_detalle"),
    path("articulos/<int:pk>/editar/", views.articulo_form, name="articulo_editar"),
    path("articulos/<int:pk>/borrar/", views.articulo_borrar, name="articulo_borrar"),
    path("articulos/<int:articulo_pk>/variantes/nueva/", views.variante_form, name="variante_nueva"),
    path("articulos/<int:articulo_pk>/variantes/<int:pk>/editar/", views.variante_form, name="variante_editar"),
    path("variantes/<int:pk>/borrar/", views.variante_borrar, name="variante_borrar"),
    path("stock/", views.stock_lista, name="stock_lista"),
    path("stock/ajuste/", views.stock_ajuste, name="stock_ajuste"),
    path("stock/traspaso/", views.stock_traspaso, name="stock_traspaso"),
    # Clientes y proveedores
    path("clientes/", views.clientes, name="clientes"),
    path("clientes/nuevo/", views.cliente_form, name="cliente_nuevo"),
    path("clientes/<int:pk>/editar/", views.cliente_form, name="cliente_editar"),
    path("clientes/<int:pk>/borrar/", views.cliente_borrar, name="cliente_borrar"),
    path("proveedores/", views.proveedores, name="proveedores"),
    path("proveedores/nuevo/", views.proveedor_form, name="proveedor_nuevo"),
    path("proveedores/<int:pk>/editar/", views.proveedor_form, name="proveedor_editar"),
    path("proveedores/<int:pk>/borrar/", views.proveedor_borrar, name="proveedor_borrar"),
    # Ventas
    path("ventas/", views.ventas, name="ventas"),
    path("ventas/nueva/", views.venta_form, name="venta_nuevo"),
    path("ventas/<int:pk>/", views.venta_detalle, name="venta_detalle"),
    path("ventas/<int:pk>/editar/", views.venta_form, name="venta_editar"),
    path("ventas/<int:pk>/borrar/", views.venta_borrar, name="venta_borrar"),
    path("ventas/<int:pk>/pdf/", views.venta_pdf, name="venta_pdf"),
    path("ventas/<int:pk>/email/", views.venta_email, name="venta_email"),
    path("ventas/<int:pk>/estado/", views.venta_estado, name="venta_estado"),
    # Compras
    path("compras/", views.compras, name="compras"),
    path("compras/nueva/", views.compra_form, name="compra_nuevo"),
    path("compras/<int:pk>/", views.compra_detalle, name="compra_detalle"),
    path("compras/<int:pk>/editar/", views.compra_form, name="compra_editar"),
    path("compras/<int:pk>/borrar/", views.compra_borrar, name="compra_borrar"),
    path("compras/<int:pk>/estado/", views.compra_estado, name="compra_estado"),
    # Gastos
    path("gastos/", views.gastos, name="gastos"),
    path("gastos/nuevo/", views.gasto_form, name="gasto_nuevo"),
    path("gastos/<int:pk>/editar/", views.gasto_form, name="gasto_editar"),
    path("gastos/<int:pk>/borrar/", views.gasto_borrar, name="gasto_borrar"),
    # Empleados y nóminas
    path("empleados/", views.empleados, name="empleados"),
    path("empleados/nuevo/", views.empleado_form, name="empleado_nuevo"),
    path("empleados/<int:pk>/editar/", views.empleado_form, name="empleado_editar"),
    path("empleados/<int:pk>/borrar/", views.empleado_borrar, name="empleado_borrar"),
    path("nominas/", views.nominas, name="nominas"),
    path("nominas/nueva/", views.nomina_form, name="nomina_nuevo"),
    path("nominas/<int:pk>/editar/", views.nomina_form, name="nomina_editar"),
    path("nominas/<int:pk>/borrar/", views.nomina_borrar, name="nomina_borrar"),
    path("nominas/<int:pk>/pdf/", views.nomina_pdf, name="nomina_pdf"),
    # Facturas
    path("facturas/", views.facturas, name="facturas"),
    path("facturas/subir/", views.factura_subir, name="factura_subir"),
    path("facturas/<int:pk>/revisar/", views.factura_revisar, name="factura_revisar"),
    path("facturas/<int:pk>/descartar/", views.factura_descartar, name="factura_descartar"),
    path("facturas/<int:pk>/borrar/", views.factura_borrar, name="factura_borrar"),
    # Configuración
    path("configuracion/", views.configuracion, name="configuracion"),
    path("configuracion/tiendas/nueva/", views.tienda_form, name="tienda_nueva"),
    path("configuracion/tiendas/<int:pk>/editar/", views.tienda_form, name="tienda_editar"),
    path("configuracion/familias/nueva/", views.familia_form, name="familia_nueva"),
    path("configuracion/familias/<int:pk>/editar/", views.familia_form, name="familia_editar"),
    # Informes y gestoría
    path("informes/", views.informes, name="informes"),
    path("informes/exportar/<str:tipo>/<str:fmt>/", views.exportar, name="exportar"),
    path("gestoria/", views.gestoria, name="gestoria"),
    path("gestoria/descargar/", views.gestoria_zip, name="gestoria_zip"),
    # Backup
    path("backup/", views.backup, name="backup"),
    # Notificaciones
    path("notificaciones/", views.notificaciones, name="notificaciones"),
    # Arqueo de caja
    path("arqueos/", views.arqueos, name="arqueos"),
    path("arqueos/nuevo/", views.arqueo_form, name="arqueo_nuevo"),
    path("arqueos/<int:pk>/editar/", views.arqueo_form, name="arqueo_editar"),
    path("arqueos/<int:pk>/borrar/", views.arqueo_borrar, name="arqueo_borrar"),
    # Devoluciones
    path("devoluciones/", views.devoluciones, name="devoluciones"),
    path("devoluciones/nueva/", views.devolucion_form, name="devolucion_nueva"),
    path("devoluciones/<int:pk>/editar/", views.devolucion_form, name="devolucion_editar"),
    path("devoluciones/<int:pk>/borrar/", views.devolucion_borrar, name="devolucion_borrar"),
    # Inventario físico
    path("inventarios/", views.inventarios, name="inventarios"),
    path("inventarios/nuevo/", views.inventario_form, name="inventario_nuevo"),
    path("inventarios/<int:pk>/", views.inventario_form, name="inventario_editar"),
    path("inventarios/<int:pk>/contar/", views.inventario_contar, name="inventario_contar"),
    path("inventarios/<int:pk>/completar/", views.inventario_completar, name="inventario_completar"),
    path("inventarios/<int:pk>/borrar/", views.inventario_borrar, name="inventario_borrar"),
    # Medidas de cliente
    path("clientes/<int:cliente_pk>/medidas/", views.medidas_cliente, name="medidas_cliente"),
    path("clientes/<int:cliente_pk>/medidas/nueva/", views.medida_form, name="medida_nueva"),
    path("clientes/<int:cliente_pk>/medidas/<int:pk>/editar/", views.medida_form, name="medida_editar"),
    # Eventos
    path("eventos/", views.eventos, name="eventos"),
    path("eventos/nuevo/", views.evento_form, name="evento_nuevo"),
    path("eventos/<int:pk>/editar/", views.evento_form, name="evento_editar"),
    path("eventos/<int:pk>/borrar/", views.evento_borrar, name="evento_borrar"),
    # Etiquetas
    path("etiquetas/", views.etiquetas, name="etiquetas"),
    # Comparativa
    path("comparativa/", views.comparativa, name="comparativa"),
    # Reportes avanzados
    path("reportes/", views.reportes_avanzados, name="reportes_avanzados"),
    path("backup/descargar/", views.backup_descargar, name="backup_descargar"),
    path("backup/enviar/", views.backup_email, name="backup_email"),
]
