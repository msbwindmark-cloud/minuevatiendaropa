from django import forms
from django.forms import inlineformset_factory

from core.models import TenantModel
from .models import (
    Articulo,
    Cliente,
    Compra,
    Empleado,
    FacturaImportada,
    Familia,
    Gasto,
    LineaCompra,
    LineaVenta,
    Nomina,
    Proveedor,
    Tienda,
    Variante,
    Venta,
)


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault("class", "form-control")
            else:
                widget.attrs.setdefault("class", "form-control")
            if isinstance(widget, forms.DateInput):
                widget.input_type = "date"
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 2)


class TenantForm(BootstrapMixin, forms.ModelForm):
    """Filtra los desplegables por la organización activa."""

    def __init__(self, *args, organizacion=None, **kwargs):
        self.organizacion = organizacion
        super().__init__(*args, **kwargs)
        if organizacion is not None:
            for field in self.fields.values():
                qs = getattr(field, "queryset", None)
                if qs is None:
                    continue
                model = getattr(qs, "model", None)
                if model is not None and issubclass(model, TenantModel):
                    field.queryset = model.all_objects.filter(organizacion=organizacion)


class TiendaForm(TenantForm):
    class Meta:
        model = Tienda
        fields = ["nombre", "codigo", "direccion", "telefono", "email", "activa"]


class FamiliaForm(TenantForm):
    class Meta:
        model = Familia
        fields = ["nombre", "orden", "activa"]


class ProveedorForm(TenantForm):
    class Meta:
        model = Proveedor
        fields = [
            "nombre", "cif", "persona_contacto", "telefono", "email",
            "direccion", "web", "notas", "activo",
        ]


class ClienteForm(TenantForm):
    class Meta:
        model = Cliente
        fields = [
            "nombre", "apellidos", "nif", "email", "telefono",
            "direccion", "ciudad", "cp", "tipo", "notas", "activo",
        ]


class ArticuloForm(TenantForm):
    class Meta:
        model = Articulo
        fields = [
            "referencia", "nombre", "familia", "proveedor", "marca", "descripcion",
            "coste", "pvp", "iva_pct", "stock_minimo", "imagen", "activo",
        ]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 2})}


class VarianteForm(TenantForm):
    class Meta:
        model = Variante
        fields = ["articulo", "talla", "color", "codigo_barras", "activa"]


class VentaForm(TenantForm):
    descontar_stock = forms.BooleanField(
        required=False,
        initial=True,
        label="Descontar stock de las líneas",
        help_text="Solo se aplica al crear la venta.",
    )

    class Meta:
        model = Venta
        fields = [
            "numero", "fecha", "tienda", "cliente", "tipo", "origen",
            "base", "iva_pct", "total", "forma_pago", "estado", "archivo", "notas",
        ]
        widgets = {"notas": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        datos = super().clean()
        base = datos.get("base") or 0
        total = datos.get("total") or 0
        iva_pct = datos.get("iva_pct") or 0
        if not total and base:
            datos["total"] = round(base * (1 + iva_pct / 100), 2)
        if total and not base:
            datos["base"] = round(total / (1 + iva_pct / 100), 2)
        return datos


class LineaVentaForm(TenantForm):
    class Meta:
        model = LineaVenta
        fields = ["articulo", "variante", "descripcion", "cantidad", "precio_unitario", "descuento_pct", "iva_pct"]


class CompraForm(TenantForm):
    class Meta:
        model = Compra
        fields = [
            "numero", "fecha", "proveedor", "base", "iva_pct", "total",
            "forma_pago", "estado", "recibida", "archivo", "notas",
        ]
        widgets = {"notas": forms.Textarea(attrs={"rows": 2})}


class LineaCompraForm(TenantForm):
    class Meta:
        model = LineaCompra
        fields = ["articulo", "variante", "descripcion", "cantidad", "coste_unitario", "iva_pct"]


class GastoForm(TenantForm):
    class Meta:
        model = Gasto
        fields = [
            "fecha", "categoria", "proveedor", "proveedor_nombre", "descripcion",
            "base", "iva_pct", "total", "forma_pago", "tienda", "recurrente", "archivo", "notas",
        ]
        widgets = {"notas": forms.Textarea(attrs={"rows": 2})}


class EmpleadoForm(TenantForm):
    class Meta:
        model = Empleado
        fields = [
            "nombre", "apellidos", "nif", "nss", "email", "telefono", "puesto",
            "tienda", "fecha_alta", "fecha_baja", "salario_bruto_anual", "activo", "notas",
        ]


class NominaForm(TenantForm):
    class Meta:
        model = Nomina
        fields = [
            "empleado", "periodo", "salario_base", "complementos", "prorrateo_pagas",
            "bruto", "irpf_pct", "irpf", "ss_empleado", "ss_empresa",
            "otras_deducciones", "neto", "estado", "archivo", "notas",
        ]
        widgets = {"periodo": forms.DateInput(attrs={"type": "date"}), "notas": forms.Textarea(attrs={"rows": 2})}


class FacturaImportadaForm(TenantForm):
    class Meta:
        model = FacturaImportada
        fields = ["archivo", "tipo"]


class AjusteStockForm(forms.Form):
    variante = forms.ModelChoiceField(queryset=Variante.objects.none(), label="Variante")
    tienda = forms.ModelChoiceField(queryset=Tienda.objects.none(), label="Tienda")
    tipo = forms.ChoiceField(
        choices=[
            ("entrada", "Entrada"),
            ("salida", "Salida"),
            ("ajuste", "Ajuste (indica el signo)"),
            ("devolucion", "Devolución"),
        ],
        initial="entrada",
    )
    cantidad = forms.IntegerField(min_value=1, initial=1)
    motivo = forms.CharField(max_length=200, required=False)

    def __init__(self, *args, organizacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizacion is not None:
            self.fields["variante"].queryset = Variante.all_objects.filter(organizacion=organizacion).select_related("articulo")
            self.fields["tienda"].queryset = Tienda.all_objects.filter(organizacion=organizacion, activa=True)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field.widget, forms.Select) else "form-control")


class TraspasoForm(forms.Form):
    variante = forms.ModelChoiceField(queryset=Variante.objects.none(), label="Variante")
    origen = forms.ModelChoiceField(queryset=Tienda.objects.none(), label="Tienda origen")
    destino = forms.ModelChoiceField(queryset=Tienda.objects.none(), label="Tienda destino")
    cantidad = forms.IntegerField(min_value=1, initial=1)
    motivo = forms.CharField(max_length=200, required=False, initial="Traspaso entre tiendas")

    def __init__(self, *args, organizacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organizacion is not None:
            self.fields["variante"].queryset = Variante.all_objects.filter(organizacion=organizacion).select_related("articulo")
            self.fields["origen"].queryset = Tienda.all_objects.filter(organizacion=organizacion, activa=True)
            self.fields["destino"].queryset = Tienda.all_objects.filter(organizacion=organizacion, activa=True)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field.widget, forms.Select) else "form-control")

    def clean(self):
        datos = super().clean()
        if datos.get("origen") and datos.get("destino") and datos["origen"] == datos["destino"]:
            raise forms.ValidationError("La tienda de origen y destino deben ser distintas.")
        return datos


LineaVentaFormSet = inlineformset_factory(
    Venta, LineaVenta, form=LineaVentaForm, extra=3, can_delete=True
)
LineaCompraFormSet = inlineformset_factory(
    Compra, LineaCompra, form=LineaCompraForm, extra=3, can_delete=True
)
