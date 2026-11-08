from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.db import models, transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from core.models import TenantModel

D = Decimal
DOS = D("0.01")


def eur(valor):
    if valor is None:
        return "0,00 €"
    return f"{valor:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def redondear(valor):
    return D(valor or 0).quantize(DOS, rounding=ROUND_HALF_UP)


IVA_CHOICES = [
    (D("21.00"), "21 %"),
    (D("10.00"), "10 %"),
    (D("4.00"), "4 %"),
    (D("0.00"), "0 %"),
]

FORMA_PAGO = [
    ("efectivo", "Efectivo"),
    ("tarjeta", "Tarjeta"),
    ("transferencia", "Transferencia"),
    ("bizum", "Bizum"),
    ("domiciliado", "Domiciliado"),
    ("otro", "Otro"),
]


class Tienda(TenantModel):
    nombre = models.CharField(max_length=120)
    codigo = models.CharField(max_length=10, help_text="Código corto para numerar facturas (ej. NER)")
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Tienda"
        verbose_name_plural = "Tiendas"
        ordering = ["nombre"]
        unique_together = [("organizacion", "codigo")]

    def __str__(self):
        return self.nombre


class Familia(TenantModel):
    nombre = models.CharField(max_length=80)
    orden = models.PositiveIntegerField(default=0)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Familia"
        verbose_name_plural = "Familias"
        ordering = ["orden", "nombre"]
        unique_together = [("organizacion", "nombre")]

    def __str__(self):
        return self.nombre


class Proveedor(TenantModel):
    nombre = models.CharField(max_length=150)
    cif = models.CharField("CIF/NIF", max_length=20, blank=True)
    persona_contacto = models.CharField(max_length=120, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    web = models.URLField(blank=True)
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Cliente(TenantModel):
    TIPO = [("particular", "Particular"), ("empresa", "Empresa")]
    nombre = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=150, blank=True)
    nif = models.CharField("NIF/CIF", max_length=20, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    ciudad = models.CharField(max_length=80, blank=True, default="Sevilla")
    cp = models.CharField("C.P.", max_length=10, blank=True)
    tipo = models.CharField(max_length=12, choices=TIPO, default="particular")
    notas = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ["nombre", "apellidos"]

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}".strip()


class Articulo(TenantModel):
    referencia = models.CharField(max_length=40)
    nombre = models.CharField(max_length=150)
    familia = models.ForeignKey(Familia, on_delete=models.PROTECT, related_name="articulos")
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name="articulos"
    )
    marca = models.CharField(max_length=80, blank=True, default="Bosselli")
    descripcion = models.TextField(blank=True)
    coste = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pvp = models.DecimalField("PVP (IVA incl.)", max_digits=10, decimal_places=2, default=0)
    iva_pct = models.DecimalField("IVA %", max_digits=4, decimal_places=2, choices=IVA_CHOICES, default=21)
    stock_minimo = models.PositiveIntegerField(default=1)
    imagen = models.ImageField(upload_to="articulos/", blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Artículo"
        verbose_name_plural = "Artículos"
        ordering = ["nombre"]
        unique_together = [("organizacion", "referencia")]

    def __str__(self):
        return f"{self.referencia} · {self.nombre}"

    def get_absolute_url(self):
        return reverse("articulo_detalle", args=[self.pk])

    @property
    def margen(self):
        if not self.pvp:
            return 0
        return redondear((self.pvp - self.coste) / self.pvp * 100)

    @property
    def stock_total(self):
        return sum(v.stock_total for v in self.variantes.all())

    @property
    def bajo_minimo(self):
        return self.stock_total <= self.stock_minimo

    @property
    def pvp_base(self):
        return redondear(self.pvp / (1 + self.iva_pct / 100))


class Variante(TenantModel):
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name="variantes")
    talla = models.CharField(max_length=20)
    color = models.CharField(max_length=50, blank=True)
    codigo_barras = models.CharField(max_length=40, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Variante"
        verbose_name_plural = "Variantes"
        ordering = ["articulo__nombre", "talla", "color"]
        unique_together = [("articulo", "talla", "color")]

    def __str__(self):
        partes = [self.articulo.nombre, self.talla]
        if self.color:
            partes.append(self.color)
        return " · ".join(partes)

    @property
    def stock_total(self):
        return sum(s.cantidad for s in self.stocks.all())


class Stock(TenantModel):
    variante = models.ForeignKey(Variante, on_delete=models.CASCADE, related_name="stocks")
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name="stocks")
    cantidad = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Stock"
        verbose_name_plural = "Stocks"
        ordering = ["variante__articulo__nombre", "variante__talla"]
        unique_together = [("variante", "tienda")]

    def __str__(self):
        return f"{self.variante} · {self.tienda}: {self.cantidad}"

    @property
    def valor_coste(self):
        return redondear(self.cantidad * self.variante.articulo.coste)

    @property
    def valor_pvp(self):
        return redondear(self.cantidad * self.variante.articulo.pvp)


class MovimientoStock(TenantModel):
    TIPOS = [
        ("entrada", "Entrada"),
        ("salida", "Salida"),
        ("ajuste", "Ajuste"),
        ("traspaso_entrada", "Traspaso (entrada)"),
        ("traspaso_salida", "Traspaso (salida)"),
        ("devolucion", "Devolución"),
    ]
    variante = models.ForeignKey(Variante, on_delete=models.CASCADE, related_name="movimientos")
    tienda = models.ForeignKey(Tienda, on_delete=models.CASCADE, related_name="movimientos")
    tipo = models.CharField(max_length=20, choices=TIPOS, default="ajuste")
    cantidad = models.IntegerField(help_text="Positivo entra, negativo sale")
    motivo = models.CharField(max_length=200, blank=True)
    referencia = models.CharField(max_length=80, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Movimiento de stock"
        verbose_name_plural = "Movimientos de stock"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.cantidad:+d} · {self.variante} · {self.tienda}"

    def save(self, *args, **kwargs):
        crear = self._state.adding
        super().save(*args, **kwargs)
        if crear and self.cantidad:
            stock, _ = Stock.all_objects.get_or_create(
                organizacion=self.organizacion,
                variante=self.variante,
                tienda=self.tienda,
                defaults={"cantidad": 0},
            )
            Stock.all_objects.filter(pk=stock.pk).update(cantidad=F("cantidad") + self.cantidad)


def mover_stock(variante, tienda, cantidad, tipo, motivo="", referencia="", usuario=None, organizacion=None):
    """Crea un movimiento y actualiza el stock. cantidad positiva entra, negativa sale."""
    org = organizacion or variante.organizacion
    return MovimientoStock.all_objects.create(
        organizacion=org,
        variante=variante,
        tienda=tienda,
        tipo=tipo,
        cantidad=cantidad,
        motivo=motivo,
        referencia=referencia,
        usuario=usuario,
    )


class Venta(TenantModel):
    TIPOS = [("ticket", "Ticket"), ("factura", "Factura"), ("resumen", "Resumen / online")]
    ORIGENES = [("tienda", "Tienda"), ("online", "Web"), ("otro", "Otro")]
    ESTADOS = [("emitida", "Emitida"), ("cobrada", "Cobrada"), ("anulada", "Anulada")]

    numero = models.CharField(max_length=30, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    tienda = models.ForeignKey(Tienda, on_delete=models.PROTECT, related_name="ventas")
    cliente = models.ForeignKey(
        Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name="ventas"
    )
    tipo = models.CharField(max_length=12, choices=TIPOS, default="ticket")
    origen = models.CharField(max_length=10, choices=ORIGENES, default="tienda")
    base = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    iva_pct = models.DecimalField("IVA %", max_digits=4, decimal_places=2, default=21)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO, default="tarjeta")
    estado = models.CharField(max_length=12, choices=ESTADOS, default="cobrada")
    archivo = models.FileField(upload_to="ventas/%Y/%m/", blank=True, null=True)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ["-fecha", "-id"]
        unique_together = [("organizacion", "numero")]

    def __str__(self):
        return f"{self.numero or 'Venta'} · {eur(self.total)}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._siguiente_numero()
        if not self.total and self.base:
            self.total = redondear(self.base * (1 + self.iva_pct / 100))
        elif self.total and not self.base:
            self.base = redondear(self.total / (1 + self.iva_pct / 100))
        super().save(*args, **kwargs)

    def _siguiente_numero(self):
        prefijo = "F" if self.tipo == "factura" else "T"
        codigo = self.tienda.codigo if self.tienda_id else "GEN"
        anyo = (self.fecha or timezone.localdate()).year
        base = f"{prefijo}{codigo}-{anyo}-"
        ultimos = (
            Venta.all_objects.filter(organizacion=self.organizacion, numero__startswith=base)
            .order_by("-id")
            .values_list("numero", flat=True)
            .first()
        )
        siguiente = 1
        if ultimos:
            try:
                siguiente = int(ultimos.split("-")[-1]) + 1
            except ValueError:
                siguiente = 1
        return f"{base}{siguiente:04d}"

    @property
    def iva_cuota(self):
        return redondear(self.total - self.base)

    def recalcular(self, guardar=True):
        lineas = list(self.lineas.all())
        if not lineas:
            return
        total = sum((l.total for l in lineas), D("0"))
        base = sum((l.base for l in lineas), D("0"))
        self.total = redondear(total)
        self.base = redondear(base)
        if self.base:
            self.iva_pct = redondear((self.total - self.base) / self.base * 100)
        if guardar and self.pk:
            self.save(update_fields=["total", "base", "iva_pct", "actualizado"])


class LineaVenta(TenantModel):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="lineas")
    articulo = models.ForeignKey(
        Articulo, on_delete=models.SET_NULL, null=True, blank=True, related_name="lineas_venta"
    )
    variante = models.ForeignKey(
        Variante, on_delete=models.SET_NULL, null=True, blank=True, related_name="lineas_venta"
    )
    descripcion = models.CharField(max_length=200)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField("PVP unitario", max_digits=10, decimal_places=2, default=0)
    descuento_pct = models.DecimalField("Dto. %", max_digits=5, decimal_places=2, default=0)
    iva_pct = models.DecimalField("IVA %", max_digits=4, decimal_places=2, default=21)

    class Meta:
        verbose_name = "Línea de venta"
        verbose_name_plural = "Líneas de venta"
        ordering = ["id"]

    def __str__(self):
        return self.descripcion

    @property
    def total(self):
        bruto = self.cantidad * self.precio_unitario
        return redondear(bruto * (1 - self.descuento_pct / 100))

    @property
    def base(self):
        return redondear(self.total / (1 + self.iva_pct / 100))


class Compra(TenantModel):
    ESTADOS = [("pendiente", "Pendiente de pago"), ("pagada", "Pagada"), ("anulada", "Anulada")]
    numero = models.CharField("Nº factura", max_length=40, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="compras")
    base = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    iva_pct = models.DecimalField("IVA %", max_digits=4, decimal_places=2, default=21)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO, default="transferencia")
    estado = models.CharField(max_length=12, choices=ESTADOS, default="pendiente")
    recibida = models.BooleanField(default=False, help_text="Si está marcada, la mercancía ya entró en stock")
    archivo = models.FileField(upload_to="compras/%Y/%m/", blank=True, null=True)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ["-fecha", "-id"]
        unique_together = [("organizacion", "numero")]

    def __str__(self):
        return f"{self.numero or 'Compra'} · {self.proveedor} · {eur(self.total)}"

    def save(self, *args, **kwargs):
        if not self.numero:
            anyo = (self.fecha or timezone.localdate()).year
            base = f"C-{anyo}-"
            ultimos = (
                Compra.all_objects.filter(organizacion=self.organizacion, numero__startswith=base)
                .order_by("-id")
                .values_list("numero", flat=True)
                .first()
            )
            siguiente = 1
            if ultimos:
                try:
                    siguiente = int(ultimos.split("-")[-1]) + 1
                except ValueError:
                    siguiente = 1
            self.numero = f"{base}{siguiente:04d}"
        if not self.total and self.base:
            self.total = redondear(self.base * (1 + self.iva_pct / 100))
        elif self.total and not self.base:
            self.base = redondear(self.total / (1 + self.iva_pct / 100))
        super().save(*args, **kwargs)

    @property
    def iva_cuota(self):
        return redondear(self.total - self.base)

    def recalcular(self, guardar=True):
        lineas = list(self.lineas.all())
        if not lineas:
            return
        total = sum((l.total for l in lineas), D("0"))
        base = sum((l.base for l in lineas), D("0"))
        self.total = redondear(total)
        self.base = redondear(base)
        if self.base:
            self.iva_pct = redondear((self.total - self.base) / self.base * 100)
        if guardar and self.pk:
            self.save(update_fields=["total", "base", "iva_pct", "actualizado"])


class LineaCompra(TenantModel):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="lineas")
    articulo = models.ForeignKey(
        Articulo, on_delete=models.SET_NULL, null=True, blank=True, related_name="lineas_compra"
    )
    variante = models.ForeignKey(
        Variante, on_delete=models.SET_NULL, null=True, blank=True, related_name="lineas_compra"
    )
    descripcion = models.CharField(max_length=200)
    cantidad = models.PositiveIntegerField(default=1)
    coste_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    iva_pct = models.DecimalField("IVA %", max_digits=4, decimal_places=2, default=21)

    class Meta:
        verbose_name = "Línea de compra"
        verbose_name_plural = "Líneas de compra"
        ordering = ["id"]

    def __str__(self):
        return self.descripcion

    @property
    def total(self):
        return redondear(self.cantidad * self.coste_unitario * (1 + self.iva_pct / 100))

    @property
    def base(self):
        return redondear(self.cantidad * self.coste_unitario)


class Gasto(TenantModel):
    CATEGORIAS = [
        ("alquiler", "Alquiler"),
        ("suministros", "Suministros"),
        ("seguros", "Seguros"),
        ("servicios", "Servicios profesionales"),
        ("publicidad", "Publicidad y marketing"),
        ("transporte", "Transporte"),
        ("personal", "Personal"),
        ("impuestos", "Impuestos y tasas"),
        ("mantenimiento", "Mantenimiento"),
        ("compras", "Compras y mercancía"),
        ("otros", "Otros"),
    ]
    fecha = models.DateField(default=timezone.localdate)
    categoria = models.CharField(max_length=20, choices=CATEGORIAS, default="otros")
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.SET_NULL, null=True, blank=True, related_name="gastos"
    )
    proveedor_nombre = models.CharField(max_length=150, blank=True)
    descripcion = models.CharField(max_length=255)
    base = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    iva_pct = models.DecimalField("IVA %", max_digits=4, decimal_places=2, default=21)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    forma_pago = models.CharField(max_length=20, choices=FORMA_PAGO, default="transferencia")
    tienda = models.ForeignKey(
        Tienda, on_delete=models.SET_NULL, null=True, blank=True, related_name="gastos"
    )
    recurrente = models.BooleanField(default=False)
    archivo = models.FileField(upload_to="gastos/%Y/%m/", blank=True, null=True)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Gasto"
        verbose_name_plural = "Gastos"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.descripcion} · {eur(self.total)}"

    def save(self, *args, **kwargs):
        if not self.total and self.base:
            self.total = redondear(self.base * (1 + self.iva_pct / 100))
        elif self.total and not self.base:
            self.base = redondear(self.total / (1 + self.iva_pct / 100))
        super().save(*args, **kwargs)

    @property
    def iva_cuota(self):
        return redondear(self.total - self.base)

    @property
    def nombre_proveedor(self):
        return self.proveedor.nombre if self.proveedor else self.proveedor_nombre


class Empleado(TenantModel):
    nombre = models.CharField(max_length=120)
    apellidos = models.CharField(max_length=150)
    nif = models.CharField("NIF/NIE", max_length=20, blank=True)
    nss = models.CharField("Nº Seguridad Social", max_length=30, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    puesto = models.CharField(max_length=100, blank=True)
    tienda = models.ForeignKey(
        Tienda, on_delete=models.SET_NULL, null=True, blank=True, related_name="empleados"
    )
    fecha_alta = models.DateField(default=timezone.localdate)
    fecha_baja = models.DateField(null=True, blank=True)
    salario_bruto_anual = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Empleado"
        verbose_name_plural = "Empleados"
        ordering = ["apellidos", "nombre"]

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}".strip()


class Nomina(TenantModel):
    ESTADOS = [("borrador", "Borrador"), ("pagada", "Pagada")]
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name="nominas")
    periodo = models.DateField(help_text="Primer día del mes")
    salario_base = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    complementos = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prorrateo_pagas = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bruto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    irpf_pct = models.DecimalField("IRPF %", max_digits=5, decimal_places=2, default=0)
    irpf = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ss_empleado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ss_empresa = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    otras_deducciones = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    neto = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=ESTADOS, default="borrador")
    archivo = models.FileField(upload_to="nominas/%Y/%m/", blank=True, null=True)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Nómina"
        verbose_name_plural = "Nóminas"
        ordering = ["-periodo", "empleado__apellidos"]
        unique_together = [("empleado", "periodo")]

    def __str__(self):
        return f"{self.empleado} · {self.periodo:%m/%Y}"

    def save(self, *args, **kwargs):
        if not self.bruto:
            self.bruto = redondear(self.salario_base + self.complementos + self.prorrateo_pagas)
        if self.bruto and not self.irpf:
            self.irpf = redondear(self.bruto * self.irpf_pct / 100)
        if not self.neto:
            self.neto = redondear(self.bruto - self.irpf - self.ss_empleado - self.otras_deducciones)
        super().save(*args, **kwargs)


class FacturaImportada(TenantModel):
    """Factura subida pendiente de revisar (compra, gasto o venta)."""

    TIPOS = [("auto", "Detectar automáticamente"), ("compra", "Compra"), ("gasto", "Gasto"), ("venta", "Venta")]
    ESTADOS = [("pendiente", "Pendiente"), ("revisada", "Revisada"), ("descartada", "Descartada")]

    archivo = models.FileField(upload_to="facturas/%Y/%m/")
    tipo = models.CharField(max_length=10, choices=TIPOS, default="auto")
    estado = models.CharField(max_length=12, choices=ESTADOS, default="pendiente")
    texto = models.TextField(blank=True)
    datos = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    procesada = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Factura importada"
        verbose_name_plural = "Facturas importadas"
        ordering = ["-creado"]

    def __str__(self):
        return f"Factura {self.pk} · {self.archivo.name}"

    def procesar(self):
        from .facturas import extraer_datos

        datos, texto, error = extraer_datos(self.archivo.path)
        self.texto = texto or ""
        self.datos = datos or {}
        self.error = error or ""
        if datos.get("tipo") and self.tipo == "auto":
            self.tipo = datos["tipo"]
        self.procesada = timezone.now()
        self.save(update_fields=["texto", "datos", "error", "tipo", "procesada", "actualizado"])
        return datos
