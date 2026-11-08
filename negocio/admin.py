from django.contrib import admin

from .models import (
    ArqueoCaja,
    Articulo,
    Cliente,
    Compra,
    Devolucion,
    Empleado,
    Evento,
    FacturaImportada,
    Familia,
    Gasto,
    InventarioFisico,
    LineaCompra,
    LineaDevolucion,
    LineaInventario,
    LineaVenta,
    MedidaCliente,
    MovimientoStock,
    Nomina,
    Proveedor,
    Stock,
    Tienda,
    Variante,
    Venta,
)


@admin.register(Tienda)
class TiendaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "direccion", "telefono", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "codigo", "direccion")


@admin.register(Familia)
class FamiliaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "orden", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cif", "persona_contacto", "telefono", "email", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "cif", "email")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellidos", "nif", "email", "telefono", "ciudad", "tipo", "activo")
    list_filter = ("tipo", "activo", "ciudad")
    search_fields = ("nombre", "apellidos", "nif", "email", "telefono")


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = ("referencia", "nombre", "familia", "proveedor", "coste", "pvp", "iva_pct", "stock_minimo", "activo")
    list_filter = ("familia", "activo", "proveedor")
    search_fields = ("referencia", "nombre", "marca")
    autocomplete_fields = ("familia", "proveedor")


class VarianteInline(admin.TabularInline):
    model = Variante
    extra = 1


@admin.register(Variante)
class VarianteAdmin(admin.ModelAdmin):
    list_display = ("articulo", "talla", "color", "codigo_barras", "activa")
    list_filter = ("activa", "articulo__familia")
    search_fields = ("articulo__nombre", "talla", "color", "codigo_barras")
    autocomplete_fields = ("articulo",)


class StockInline(admin.TabularInline):
    model = Stock
    extra = 1


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("variante", "tienda", "cantidad")
    list_filter = ("tienda",)
    search_fields = ("variante__articulo__nombre", "variante__talla", "tienda__nombre")
    autocomplete_fields = ("variante", "tienda")


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "variante", "tienda", "cantidad", "motivo", "usuario")
    list_filter = ("tipo", "tienda", "fecha")
    search_fields = ("variante__articulo__nombre", "motivo", "referencia")
    date_hierarchy = "fecha"
    readonly_fields = ("fecha",)


class LineaVentaInline(admin.TabularInline):
    model = LineaVenta
    extra = 1
    autocomplete_fields = ("articulo", "variante")


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("numero", "fecha", "tienda", "cliente", "tipo", "origen", "base", "total", "forma_pago", "estado")
    list_filter = ("tipo", "origen", "estado", "forma_pago", "tienda", "fecha")
    search_fields = ("numero", "cliente__nombre", "cliente__apellidos", "notas")
    date_hierarchy = "fecha"
    inlines = [LineaVentaInline]
    autocomplete_fields = ("tienda", "cliente")


@admin.register(LineaVenta)
class LineaVentaAdmin(admin.ModelAdmin):
    list_display = ("venta", "descripcion", "cantidad", "precio_unitario", "descuento_pct", "iva_pct")
    search_fields = ("descripcion", "venta__numero")
    autocomplete_fields = ("venta", "articulo", "variante")


class LineaCompraInline(admin.TabularInline):
    model = LineaCompra
    extra = 1
    autocomplete_fields = ("articulo", "variante")


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ("numero", "fecha", "proveedor", "base", "total", "forma_pago", "estado", "recibida")
    list_filter = ("estado", "recibida", "forma_pago", "fecha")
    search_fields = ("numero", "proveedor__nombre", "notas")
    date_hierarchy = "fecha"
    inlines = [LineaCompraInline]
    autocomplete_fields = ("proveedor",)


@admin.register(LineaCompra)
class LineaCompraAdmin(admin.ModelAdmin):
    list_display = ("compra", "descripcion", "cantidad", "coste_unitario", "iva_pct")
    search_fields = ("descripcion", "compra__numero")
    autocomplete_fields = ("compra", "articulo", "variante")


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "categoria", "descripcion", "proveedor", "tienda", "base", "total", "forma_pago", "recurrente")
    list_filter = ("categoria", "tienda", "recurrente", "forma_pago", "fecha")
    search_fields = ("descripcion", "proveedor_nombre", "proveedor__nombre", "notas")
    date_hierarchy = "fecha"
    autocomplete_fields = ("proveedor", "tienda")


@admin.register(Empleado)
class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "apellidos", "nif", "puesto", "tienda", "fecha_alta", "salario_bruto_anual", "activo")
    list_filter = ("activo", "tienda", "puesto")
    search_fields = ("nombre", "apellidos", "nif", "email", "telefono")
    autocomplete_fields = ("tienda",)


@admin.register(Nomina)
class NominaAdmin(admin.ModelAdmin):
    list_display = ("periodo", "empleado", "bruto", "irpf", "ss_empleado", "neto", "estado")
    list_filter = ("estado", "periodo", "empleado")
    search_fields = ("empleado__nombre", "empleado__apellidos")
    date_hierarchy = "periodo"
    autocomplete_fields = ("empleado",)


@admin.register(FacturaImportada)
class FacturaImportadaAdmin(admin.ModelAdmin):
    list_display = ("pk", "tipo", "estado", "procesada", "creado")
    list_filter = ("tipo", "estado")
    search_fields = ("texto", "datos")
    readonly_fields = ("texto", "datos", "error", "procesada", "creado", "actualizado")
    date_hierarchy = "creado"

@admin.register(ArqueoCaja)
class ArqueoCajaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tienda", "total_contado", "total_esperado", "diferencia", "estado")
    list_filter = ("tienda", "estado", "fecha")
    date_hierarchy = "fecha"


@admin.register(Devolucion)
class DevolucionAdmin(admin.ModelAdmin):
    list_display = ("pk", "venta", "fecha", "estado", "total")
    list_filter = ("estado", "fecha")
    date_hierarchy = "fecha"


@admin.register(LineaDevolucion)
class LineaDevolucionAdmin(admin.ModelAdmin):
    list_display = ("devolucion", "descripcion", "cantidad", "precio_unitario")


@admin.register(InventarioFisico)
class InventarioFisicoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tienda", "estado", "completado")
    list_filter = ("estado", "tienda", "fecha")
    date_hierarchy = "fecha"


@admin.register(LineaInventario)
class LineaInventarioAdmin(admin.ModelAdmin):
    list_display = ("inventario", "variante", "cantidad_sistema", "cantidad_contada", "diferencia")


@admin.register(MedidaCliente)
class MedidaClienteAdmin(admin.ModelAdmin):
    list_display = ("cliente", "fecha", "pecho", "cintura", "cadera", "cuello")
    list_filter = ("fecha",)
    search_fields = ("cliente__nombre", "cliente__apellidos")
    date_hierarchy = "fecha"


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "titulo", "tipo", "tienda")
    list_filter = ("tipo", "tienda", "fecha")
    search_fields = ("titulo", "descripcion")
    date_hierarchy = "fecha"