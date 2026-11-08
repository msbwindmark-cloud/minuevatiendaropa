from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.db.models import Count, F, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from core.auditoria import registrar
from core.decorators import admin_required, gestor_required
from core.models import Organizacion

from .forms import (
    AjusteStockForm,
    ArticuloForm,
    ClienteForm,
    CompraForm,
    EmpleadoForm,
    FacturaImportadaForm,
    FamiliaForm,
    GastoForm,
    LineaCompraFormSet,
    LineaVentaFormSet,
    NominaForm,
    ProveedorForm,
    TiendaForm,
    TraspasoForm,
    VarianteForm,
    VentaForm,
)
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
    Stock,
    Tienda,
    Variante,
    Venta,
    eur,
    mover_stock,
    redondear,
)

D = Decimal


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def _org(request):
    org = getattr(request, "organizacion", None)
    if org is None:
        org = Organizacion.objects.order_by("id").first()
    return org


def _qs(model, request):
    return model.all_objects.filter(organizacion=_org(request))


def _fecha(valor):
    if not valor:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    return None


def _rango(request, qs, campo="fecha"):
    desde = _fecha(request.GET.get("desde"))
    hasta = _fecha(request.GET.get("hasta"))
    if desde:
        qs = qs.filter(**{f"{campo}__gte": desde})
    if hasta:
        qs = qs.filter(**{f"{campo}__lte": hasta})
    return qs, desde, hasta


def _pagin(request, qs, por_pagina=20):
    from django.core.paginator import Paginator

    return Paginator(qs, por_pagina).get_page(request.GET.get("page"))


def _contexto_lista(request, page_obj, **extra):
    ctx = {"page_obj": page_obj, "filtros": request.GET}
    ctx.update(extra)
    return ctx


def _guardar_con_org(form, request):
    obj = form.save(commit=False)
    obj.organizacion = _org(request)
    obj.save()
    return obj


def _resolver_proveedor(org, nombre="", cif="", crear=True):
    if not nombre and not cif:
        return None
    qs = Proveedor.all_objects.filter(organizacion=org)
    proveedor = None
    if cif:
        proveedor = qs.filter(cif__iexact=cif.strip()).first()
    if proveedor is None and nombre:
        proveedor = qs.filter(nombre__iexact=nombre.strip()).first()
    if proveedor is None and crear:
        proveedor = qs.create(
            organizacion=org,
            nombre=(nombre or cif).strip()[:150],
            cif=(cif or "").strip()[:20],
        )
    return proveedor


def _adjuntar_factura(obj, request):
    """Si se crea desde una factura importada, reutiliza el archivo y la marca revisada."""
    factura_id = request.POST.get("factura_id") or request.GET.get("factura")
    if not factura_id:
        return
    factura = FacturaImportada.all_objects.filter(
        pk=factura_id, organizacion=_org(request)
    ).first()
    if factura is None:
        return
    if factura.archivo and hasattr(obj, "archivo"):
        obj.archivo.name = factura.archivo.name
        obj.save(update_fields=["archivo"])
    factura.estado = "revisada"
    factura.save(update_fields=["estado", "actualizado"])


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@login_required
def dashboard(request):
    org = _org(request)
    hoy = timezone.localdate()
    mes_ini = hoy.replace(day=1)
    anyo_ini = hoy.replace(month=1, day=1)

    ventas = _qs(Venta, request).exclude(estado="anulada")
    ventas_mes = ventas.filter(fecha__gte=mes_ini, fecha__lte=hoy)
    ventas_hoy = ventas.filter(fecha=hoy)
    compras_mes = _qs(Compra, request).exclude(estado="anulada").filter(fecha__gte=mes_ini, fecha__lte=hoy)
    gastos_mes = _qs(Gasto, request).filter(fecha__gte=mes_ini, fecha__lte=hoy)
    nominas_mes = _qs(Nomina, request).filter(periodo__gte=mes_ini, periodo__lte=hoy)

    ingresos_mes = ventas_mes.aggregate(s=Sum("total"))["s"] or D("0")
    ingresos_hoy = ventas_hoy.aggregate(s=Sum("total"))["s"] or D("0")
    compras_total = compras_mes.aggregate(s=Sum("total"))["s"] or D("0")
    gastos_total = gastos_mes.aggregate(s=Sum("total"))["s"] or D("0")
    nominas_total = nominas_mes.aggregate(s=Sum("bruto"))["s"] or D("0")
    salidas = compras_total + gastos_total + nominas_total
    beneficio = ingresos_mes - salidas
    n_ventas = ventas_mes.count()
    ticket_medio = (ingresos_mes / n_ventas) if n_ventas else D("0")

    por_tienda = list(
        ventas_mes.values("tienda__nombre").annotate(total=Sum("total"), n=Count("id")).order_by("-total")
    )
    top_articulos = list(
        LineaVenta.all_objects.filter(organizacion=org, venta__in=ventas_mes)
        .values("descripcion")
        .annotate(cantidad=Sum("cantidad"), total=Sum("precio_unitario"))
        .order_by("-cantidad")[:6]
    )

    articulos = list(
        Articulo.all_objects.filter(organizacion=org, activo=True).prefetch_related("variantes__stocks")
    )
    stock_bajo = [a for a in articulos if a.bajo_minimo]
    valor_stock = sum((a.stock_total * a.coste for a in articulos), D("0"))

    facturas_pendientes = _qs(FacturaImportada, request).filter(estado="pendiente").count()
    compras_pendientes = _qs(Compra, request).filter(estado="pendiente").count()
    nominas_borrador = _qs(Nomina, request).filter(estado="borrador").count()

    # Evolución de los últimos 6 meses
    def mes_atras(fecha, n):
        y = fecha.year + (fecha.month - 1 - n) // 12
        m = (fecha.month - 1 - n) % 12 + 1
        return date(y, m, 1)

    etiquetas, serie_ventas, serie_gastos = [], [], []
    for n in range(5, -1, -1):
        ini = mes_atras(hoy, n)
        fin = mes_atras(hoy, n - 1) if n > 0 else hoy
        etiquetas.append(ini.strftime("%b %y").capitalize())
        serie_ventas.append(
            float(ventas.filter(fecha__gte=ini, fecha__lt=fin).aggregate(s=Sum("total"))["s"] or 0)
        )
        g = _qs(Gasto, request).filter(fecha__gte=ini, fecha__lt=fin).aggregate(s=Sum("total"))["s"] or 0
        c = _qs(Compra, request).exclude(estado="anulada").filter(fecha__gte=ini, fecha__lt=fin).aggregate(s=Sum("total"))["s"] or 0
        serie_gastos.append(float(g + c))

    maximo = max(serie_ventas + serie_gastos + [1])
    barras = [
        {
            "label": etiquetas[i],
            "ventas": serie_ventas[i],
            "gastos": serie_gastos[i],
            "vp": max(3, round(serie_ventas[i] / maximo * 100)),
            "gp": max(3, round(serie_gastos[i] / maximo * 100)),
        }
        for i in range(len(etiquetas))
    ]

    ultimas_ventas = ventas.select_related("tienda", "cliente").order_by("-fecha", "-id")[:6]
    ultimas_facturas = _qs(FacturaImportada, request).order_by("-creado")[:4]

    ctx = {
        "hoy": hoy,
        "mes_ini": mes_ini,
        "ingresos_mes": ingresos_mes,
        "ingresos_hoy": ingresos_hoy,
        "compras_total": compras_total,
        "gastos_total": gastos_total,
        "nominas_total": nominas_total,
        "beneficio": beneficio,
        "ticket_medio": ticket_medio,
        "n_ventas": n_ventas,
        "por_tienda": por_tienda,
        "top_articulos": top_articulos,
        "stock_bajo": stock_bajo,
        "valor_stock": valor_stock,
        "facturas_pendientes": facturas_pendientes,
        "compras_pendientes": compras_pendientes,
        "nominas_borrador": nominas_borrador,
        "ultimas_ventas": ultimas_ventas,
        "ultimas_facturas": ultimas_facturas,
        "barras": barras,
        "chart": {"labels": etiquetas, "ventas": serie_ventas, "gastos": serie_gastos},
    }
    return render(request, "negocio/dashboard.html", ctx)


# ---------------------------------------------------------------------------
# Artículos, variantes y stock
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def articulos(request):
    qs = _qs(Articulo, request).select_related("familia", "proveedor").prefetch_related("variantes__stocks")
    q = request.GET.get("q", "").strip()
    familia = request.GET.get("familia", "")
    tienda = request.GET.get("tienda", "")
    bajo = request.GET.get("bajo", "")
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(referencia__icontains=q) | Q(marca__icontains=q))
    if familia:
        qs = qs.filter(familia_id=familia)
    if tienda:
        qs = qs.filter(variantes__stocks__tienda_id=tienda, variantes__stocks__cantidad__gt=0).distinct()
    qs = qs.annotate(stock_total_db=Sum("variantes__stocks__cantidad"))
    if bajo == "1":
        qs = qs.filter(stock_total_db__lte=F("stock_minimo"))
    qs = qs.order_by("nombre")
    page_obj = _pagin(request, qs, 24)
    return render(
        request,
        "negocio/articulos.html",
        _contexto_lista(
            request,
            page_obj,
            familias=_qs(Familia, request).filter(activa=True),
            titulo="Artículos",
        ),
    )


@login_required
@gestor_required
def articulo_detalle(request, pk):
    org = _org(request)
    articulo = get_object_or_404(
        Articulo.all_objects.select_related("familia", "proveedor").prefetch_related(
            "variantes__stocks__tienda", "variantes__movimientos__tienda"
        ),
        pk=pk,
        organizacion=org,
    )
    return render(
        request,
        "negocio/articulo_detalle.html",
        {"articulo": articulo, "tiendas": _qs(Tienda, request).filter(activa=True)},
    )


@login_required
@gestor_required
def articulo_form(request, pk=None):
    org = _org(request)
    obj = None
    if pk:
        obj = get_object_or_404(Articulo.all_objects, pk=pk, organizacion=org)
    form = ArticuloForm(request.POST or None, request.FILES or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.save()
        messages.success(request, f"Artículo «{obj.nombre}» guardado.")
        return redirect("articulo_detalle", pk=obj.pk)
    return render(
        request,
        "negocio/form.html",
        {
            "form": form,
            "titulo": "Editar artículo" if obj else "Nuevo artículo",
            "subtitulo": "Ficha de prenda, coste, PVP y stock mínimo",
            "volver": "articulos",
        },
    )


@login_required
@admin_required
@require_POST
def articulo_borrar(request, pk):
    obj = get_object_or_404(Articulo.all_objects, pk=pk, organizacion=_org(request))
    nombre = obj.nombre
    obj.delete()
    messages.success(request, f"Artículo «{nombre}» eliminado.")
    return redirect("articulos")


@login_required
@gestor_required
def variante_form(request, articulo_pk, pk=None):
    org = _org(request)
    articulo = get_object_or_404(Articulo.all_objects, pk=articulo_pk, organizacion=org)
    obj = None
    if pk:
        obj = get_object_or_404(Variante.all_objects, pk=pk, organizacion=org, articulo=articulo)
    initial = {} if obj else {"articulo": articulo}
    form = VarianteForm(
        request.POST or None, instance=obj, initial=initial, organizacion=org
    )
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.articulo = articulo
        obj.save()
        messages.success(request, "Variante guardada. Ahora puedes asignarle stock.")
        return redirect("articulo_detalle", pk=articulo.pk)
    return render(
        request,
        "negocio/form.html",
        {
            "form": form,
            "titulo": "Nueva variante" if not obj else "Editar variante",
            "subtitulo": str(articulo),
            "volver": "articulo_detalle",
            "volver_pk": articulo.pk,
        },
    )


@login_required
@admin_required
@require_POST
def variante_borrar(request, pk):
    org = _org(request)
    obj = get_object_or_404(Variante.all_objects, pk=pk, organizacion=org)
    articulo_pk = obj.articulo_id
    obj.delete()
    messages.success(request, "Variante eliminada.")
    return redirect("articulo_detalle", pk=articulo_pk)


@login_required
@gestor_required
def stock_lista(request):
    qs = _qs(Stock, request).select_related("variante__articulo", "tienda")
    q = request.GET.get("q", "").strip()
    tienda = request.GET.get("tienda", "")
    bajo = request.GET.get("bajo", "")
    if q:
        qs = qs.filter(
            Q(variante__articulo__nombre__icontains=q)
            | Q(variante__articulo__referencia__icontains=q)
            | Q(variante__talla__icontains=q)
        )
    if tienda:
        qs = qs.filter(tienda_id=tienda)
    if bajo == "1":
        qs = qs.filter(cantidad__lte=F("variante__articulo__stock_minimo"))
    qs = qs.order_by("variante__articulo__nombre", "variante__talla")
    page_obj = _pagin(request, qs, 30)
    total_unidades = qs.aggregate(s=Sum("cantidad"))["s"] or 0
    return render(
        request,
        "negocio/stock.html",
        _contexto_lista(request, page_obj, total_unidades=total_unidades),
    )


@login_required
@gestor_required
def stock_ajuste(request):
    org = _org(request)
    form = AjusteStockForm(request.POST or None, organizacion=org)
    if request.method == "POST" and form.is_valid():
        variante = form.cleaned_data["variante"]
        tienda = form.cleaned_data["tienda"]
        tipo = form.cleaned_data["tipo"]
        cantidad = form.cleaned_data["cantidad"]
        stock = Stock.all_objects.filter(organizacion=org, variante=variante, tienda=tienda).first()
        disponible = stock.cantidad if stock else 0
        if tipo == "salida" and cantidad > disponible:
            messages.error(request, f"No hay suficiente stock: solo quedan {disponible} unidades.")
        else:
            delta = -cantidad if tipo == "salida" else cantidad
            mover_stock(
                variante, tienda, delta, tipo,
                motivo=form.cleaned_data.get("motivo", ""),
                usuario=request.user, organizacion=org,
            )
            messages.success(request, "Movimiento de stock registrado.")
            return redirect("stock_lista")
    return render(
        request,
        "negocio/form.html",
        {
            "form": form,
            "titulo": "Ajustar stock",
            "subtitulo": "Entradas, salidas, devoluciones y ajustes",
            "volver": "stock_lista",
        },
    )


@login_required
@gestor_required
def stock_traspaso(request):
    org = _org(request)
    form = TraspasoForm(request.POST or None, organizacion=org)
    if request.method == "POST" and form.is_valid():
        variante = form.cleaned_data["variante"]
        origen = form.cleaned_data["origen"]
        destino = form.cleaned_data["destino"]
        cantidad = form.cleaned_data["cantidad"]
        stock = Stock.all_objects.filter(organizacion=org, variante=variante, tienda=origen).first()
        disponible = stock.cantidad if stock else 0
        if cantidad > disponible:
            messages.error(request, f"No hay suficiente stock en {origen}: solo {disponible} unidades.")
        else:
            motivo = form.cleaned_data.get("motivo") or "Traspaso entre tiendas"
            mover_stock(variante, origen, -cantidad, "traspaso_salida", motivo=motivo, usuario=request.user, organizacion=org)
            mover_stock(variante, destino, cantidad, "traspaso_entrada", motivo=motivo, usuario=request.user, organizacion=org)
            messages.success(request, f"Traspasadas {cantidad} unidades de {origen} a {destino}.")
            return redirect("stock_lista")
    return render(
        request,
        "negocio/form.html",
        {
            "form": form,
            "titulo": "Traspaso entre tiendas",
            "subtitulo": "Mueve mercancía de Nervión a Porvenir o al contrario",
            "volver": "stock_lista",
        },
    )


# ---------------------------------------------------------------------------
# Clientes y proveedores
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def clientes(request):
    qs = _qs(Cliente, request)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) | Q(apellidos__icontains=q) | Q(nif__icontains=q)
            | Q(email__icontains=q) | Q(telefono__icontains=q)
        )
    qs = qs.order_by("nombre", "apellidos")
    return render(request, "negocio/clientes.html", _contexto_lista(request, _pagin(request, qs, 25)))


@login_required
@gestor_required
def cliente_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Cliente.all_objects, pk=pk, organizacion=org) if pk else None
    form = ClienteForm(request.POST or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.save()
        messages.success(request, "Cliente guardado.")
        return redirect("clientes")
    return render(
        request,
        "negocio/form.html",
        {"form": form, "titulo": "Editar cliente" if obj else "Nuevo cliente", "volver": "clientes"},
    )


@login_required
@admin_required
@require_POST
def cliente_borrar(request, pk):
    obj = get_object_or_404(Cliente.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Cliente eliminado.")
    return redirect("clientes")


@login_required
@gestor_required
def proveedores(request):
    qs = _qs(Proveedor, request)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(cif__icontains=q) | Q(email__icontains=q))
    return render(request, "negocio/proveedores.html", _contexto_lista(request, _pagin(request, qs.order_by("nombre"), 25)))


@login_required
@gestor_required
def proveedor_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Proveedor.all_objects, pk=pk, organizacion=org) if pk else None
    form = ProveedorForm(request.POST or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.save()
        messages.success(request, "Proveedor guardado.")
        return redirect("proveedores")
    return render(
        request,
        "negocio/form.html",
        {"form": form, "titulo": "Editar proveedor" if obj else "Nuevo proveedor", "volver": "proveedores"},
    )


@login_required
@admin_required
@require_POST
def proveedor_borrar(request, pk):
    obj = get_object_or_404(Proveedor.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Proveedor eliminado.")
    return redirect("proveedores")


# ---------------------------------------------------------------------------
# Ventas
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def ventas(request):
    qs = _qs(Venta, request).select_related("tienda", "cliente")
    qs, desde, hasta = _rango(request, qs)
    tienda = request.GET.get("tienda", "")
    estado = request.GET.get("estado", "")
    tipo = request.GET.get("tipo", "")
    q = request.GET.get("q", "").strip()
    if tienda:
        qs = qs.filter(tienda_id=tienda)
    if estado:
        qs = qs.filter(estado=estado)
    if tipo:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(cliente__nombre__icontains=q) | Q(cliente__apellidos__icontains=q))
    total = qs.aggregate(s=Sum("total"))["s"] or 0
    page_obj = _pagin(request, qs.order_by("-fecha", "-id"), 25)
    return render(
        request,
        "negocio/ventas.html",
        _contexto_lista(request, page_obj, total=total, desde=desde, hasta=hasta),
    )


@login_required
@gestor_required
def venta_form(request, pk=None):
    org = _org(request)
    obj = None
    if pk:
        obj = get_object_or_404(Venta.all_objects, pk=pk, organizacion=org)

    initial = {}
    if obj is None:
        for campo in ("numero", "base", "total", "iva_pct"):
            valor = request.GET.get(campo)
            if valor:
                initial[campo] = valor
        fecha = _fecha(request.GET.get("fecha"))
        if fecha:
            initial["fecha"] = fecha
        if request.GET.get("tipo"):
            initial["tipo"] = request.GET.get("tipo")

    form = VentaForm(
        request.POST or None, request.FILES or None, instance=obj, initial=initial, organizacion=org
    )
    formset = LineaVentaFormSet(request.POST or None, instance=obj or Venta(), prefix="lineas")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        es_nueva = obj is None
        venta = form.save(commit=False)
        venta.organizacion = org
        venta.save()
        formset.instance = venta
        for linea in formset.save(commit=False):
            linea.organizacion = org
            linea.venta = venta
            linea.save()
        for borrada in formset.deleted_objects:
            borrada.delete()
        venta.recalcular()
        if es_nueva and form.cleaned_data.get("descontar_stock"):
            for linea in venta.lineas.all():
                if linea.variante_id:
                    mover_stock(
                        linea.variante, venta.tienda, -linea.cantidad, "salida",
                        motivo=f"Venta {venta.numero}", referencia=venta.numero,
                        usuario=request.user, organizacion=org,
                    )
        _adjuntar_factura(venta, request)
        messages.success(request, f"Venta {venta.numero} guardada.")
        return redirect("venta_detalle", pk=venta.pk)
    return render(
        request,
        "negocio/venta_form.html",
        {
            "form": form,
            "formset": formset,
            "titulo": "Editar venta" if obj else "Registrar venta",
            "subtitulo": "Venta de tienda, factura o resumen de la web",
            "volver": "ventas",
            "factura": request.GET.get("factura", ""),
        },
    )


@login_required
@gestor_required
def venta_detalle(request, pk):
    venta = get_object_or_404(
        Venta.all_objects.select_related("tienda", "cliente").prefetch_related("lineas"),
        pk=pk, organizacion=_org(request),
    )
    return render(request, "negocio/venta_detalle.html", {"venta": venta})


@login_required
@admin_required
@require_POST
def venta_borrar(request, pk):
    obj = get_object_or_404(Venta.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Venta eliminada.")
    return redirect("ventas")


@login_required
@gestor_required
@require_POST
def venta_estado(request, pk):
    obj = get_object_or_404(Venta.all_objects, pk=pk, organizacion=_org(request))
    nuevo = request.POST.get("estado")
    if nuevo in dict(Venta.ESTADOS):
        obj.estado = nuevo
        obj.save(update_fields=["estado", "actualizado"])
        messages.success(request, f"Venta marcada como {obj.get_estado_display().lower()}.")
    return redirect("venta_detalle", pk=obj.pk)


# ---------------------------------------------------------------------------
# Compras
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def compras(request):
    qs = _qs(Compra, request).select_related("proveedor")
    qs, desde, hasta = _rango(request, qs)
    proveedor = request.GET.get("proveedor", "")
    estado = request.GET.get("estado", "")
    q = request.GET.get("q", "").strip()
    if proveedor:
        qs = qs.filter(proveedor_id=proveedor)
    if estado:
        qs = qs.filter(estado=estado)
    if q:
        qs = qs.filter(Q(numero__icontains=q) | Q(proveedor__nombre__icontains=q))
    total = qs.aggregate(s=Sum("total"))["s"] or 0
    page_obj = _pagin(request, qs.order_by("-fecha", "-id"), 25)
    return render(
        request,
        "negocio/compras.html",
        _contexto_lista(request, page_obj, total=total, desde=desde, hasta=hasta),
    )


@login_required
@gestor_required
def compra_form(request, pk=None):
    org = _org(request)
    obj = None
    if pk:
        obj = get_object_or_404(Compra.all_objects, pk=pk, organizacion=org)

    initial = {}
    if obj is None:
        for campo in ("numero", "base", "total", "iva_pct"):
            valor = request.GET.get(campo)
            if valor:
                initial[campo] = valor
        fecha = _fecha(request.GET.get("fecha"))
        if fecha:
            initial["fecha"] = fecha
        proveedor = _resolver_proveedor(
            org, request.GET.get("proveedor_nombre", ""), request.GET.get("cif", ""), crear=False
        )
        if proveedor:
            initial["proveedor"] = proveedor

    datos_post = request.POST
    if request.method == "POST" and not request.POST.get("proveedor"):
        proveedor = _resolver_proveedor(
            org, request.GET.get("proveedor_nombre", ""), request.GET.get("cif", ""), crear=True
        )
        if proveedor:
            datos_post = request.POST.copy()
            datos_post["proveedor"] = proveedor.pk

    form = CompraForm(
        datos_post or None, request.FILES or None, instance=obj, initial=initial, organizacion=org
    )
    formset = LineaCompraFormSet(request.POST or None, instance=obj or Compra(), prefix="lineas")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        ya_recibida = bool(obj and obj.recibida)
        compra = form.save(commit=False)
        compra.organizacion = org
        compra.save()
        formset.instance = compra
        for linea in formset.save(commit=False):
            linea.organizacion = org
            linea.compra = compra
            linea.save()
        for borrada in formset.deleted_objects:
            borrada.delete()
        compra.recalcular()
        if compra.recibida and not ya_recibida:
            tienda = _qs(Tienda, request).filter(activa=True).first()
            for linea in compra.lineas.all():
                if linea.variante_id and tienda:
                    mover_stock(
                        linea.variante, tienda, linea.cantidad, "entrada",
                        motivo=f"Compra {compra.numero}", referencia=compra.numero,
                        usuario=request.user, organizacion=org,
                    )
                if linea.articulo_id and linea.coste_unitario:
                    Articulo.all_objects.filter(pk=linea.articulo_id).update(coste=linea.coste_unitario)
        _adjuntar_factura(compra, request)
        messages.success(request, f"Compra {compra.numero} guardada.")
        return redirect("compra_detalle", pk=compra.pk)
    return render(
        request,
        "negocio/compra_form.html",
        {
            "form": form,
            "formset": formset,
            "titulo": "Editar compra" if obj else "Registrar compra",
            "subtitulo": "Factura de proveedor y entrada de mercancía",
            "volver": "compras",
            "factura": request.GET.get("factura", ""),
        },
    )


@login_required
@gestor_required
def compra_detalle(request, pk):
    compra = get_object_or_404(
        Compra.all_objects.select_related("proveedor").prefetch_related("lineas"),
        pk=pk, organizacion=_org(request),
    )
    return render(request, "negocio/compra_detalle.html", {"compra": compra})


@login_required
@admin_required
@require_POST
def compra_borrar(request, pk):
    obj = get_object_or_404(Compra.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Compra eliminada.")
    return redirect("compras")


@login_required
@gestor_required
@require_POST
def compra_estado(request, pk):
    obj = get_object_or_404(Compra.all_objects, pk=pk, organizacion=_org(request))
    nuevo = request.POST.get("estado")
    if nuevo in dict(Compra.ESTADOS):
        obj.estado = nuevo
        obj.save(update_fields=["estado", "actualizado"])
        messages.success(request, "Estado de la compra actualizado.")
    return redirect("compra_detalle", pk=obj.pk)


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def gastos(request):
    qs = _qs(Gasto, request).select_related("proveedor", "tienda")
    qs, desde, hasta = _rango(request, qs)
    categoria = request.GET.get("categoria", "")
    tienda = request.GET.get("tienda", "")
    q = request.GET.get("q", "").strip()
    if categoria:
        qs = qs.filter(categoria=categoria)
    if tienda:
        qs = qs.filter(tienda_id=tienda)
    if q:
        qs = qs.filter(Q(descripcion__icontains=q) | Q(proveedor_nombre__icontains=q) | Q(proveedor__nombre__icontains=q))
    total = qs.aggregate(s=Sum("total"))["s"] or 0
    page_obj = _pagin(request, qs.order_by("-fecha", "-id"), 25)
    return render(
        request,
        "negocio/gastos.html",
        _contexto_lista(request, page_obj, total=total, desde=desde, hasta=hasta, categorias=Gasto.CATEGORIAS),
    )


@login_required
@gestor_required
def gasto_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Gasto.all_objects, pk=pk, organizacion=org) if pk else None
    initial = {}
    if obj is None:
        for campo in ("base", "total", "iva_pct", "descripcion", "proveedor_nombre"):
            valor = request.GET.get(campo)
            if valor:
                initial[campo] = valor
        fecha = _fecha(request.GET.get("fecha"))
        if fecha:
            initial["fecha"] = fecha
        if request.GET.get("categoria"):
            initial["categoria"] = request.GET.get("categoria")
        proveedor = _resolver_proveedor(
            org, request.GET.get("proveedor_nombre", ""), request.GET.get("cif", ""), crear=False
        )
        if proveedor:
            initial["proveedor"] = proveedor
    form = GastoForm(request.POST or None, request.FILES or None, instance=obj, initial=initial, organizacion=org)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.save()
        _adjuntar_factura(obj, request)
        messages.success(request, "Gasto guardado.")
        return redirect("gastos")
    return render(
        request,
        "negocio/form.html",
        {
            "form": form,
            "titulo": "Editar gasto" if obj else "Nuevo gasto",
            "subtitulo": "Alquiler, suministros, seguros, servicios...",
            "volver": "gastos",
            "factura": request.GET.get("factura", ""),
        },
    )


@login_required
@admin_required
@require_POST
def gasto_borrar(request, pk):
    obj = get_object_or_404(Gasto.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Gasto eliminado.")
    return redirect("gastos")


# ---------------------------------------------------------------------------
# Empleados y nóminas
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def empleados(request):
    qs = _qs(Empleado, request).select_related("tienda")
    q = request.GET.get("q", "").strip()
    tienda = request.GET.get("tienda", "")
    activo = request.GET.get("activo", "")
    if q:
        qs = qs.filter(Q(nombre__icontains=q) | Q(apellidos__icontains=q) | Q(nif__icontains=q))
    if tienda:
        qs = qs.filter(tienda_id=tienda)
    if activo == "1":
        qs = qs.filter(activo=True)
    elif activo == "0":
        qs = qs.filter(activo=False)
    return render(request, "negocio/empleados.html", _contexto_lista(request, _pagin(request, qs, 25)))


@login_required
@gestor_required
def empleado_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Empleado.all_objects, pk=pk, organizacion=org) if pk else None
    form = EmpleadoForm(request.POST or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.save()
        messages.success(request, "Empleado guardado.")
        return redirect("empleados")
    return render(
        request,
        "negocio/form.html",
        {"form": form, "titulo": "Editar empleado" if obj else "Nuevo empleado", "volver": "empleados"},
    )


@login_required
@admin_required
@require_POST
def empleado_borrar(request, pk):
    obj = get_object_or_404(Empleado.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Empleado eliminado.")
    return redirect("empleados")


@login_required
@gestor_required
def nominas(request):
    qs = _qs(Nomina, request).select_related("empleado", "empleado__tienda")
    anyo = request.GET.get("anyo", str(timezone.localdate().year))
    empleado = request.GET.get("empleado", "")
    estado = request.GET.get("estado", "")
    if anyo:
        qs = qs.filter(periodo__year=anyo)
    if empleado:
        qs = qs.filter(empleado_id=empleado)
    if estado:
        qs = qs.filter(estado=estado)
    total = qs.aggregate(s=Sum("neto"))["s"] or 0
    page_obj = _pagin(request, qs.order_by("-periodo", "empleado__apellidos"), 25)
    return render(
        request,
        "negocio/nominas.html",
        _contexto_lista(request, page_obj, total=total, anyo=anyo, empleados=_qs(Empleado, request)),
    )


@login_required
@gestor_required
def nomina_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Nomina.all_objects, pk=pk, organizacion=org) if pk else None
    form = NominaForm(request.POST or None, request.FILES or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.save()
        messages.success(request, "Nómina guardada.")
        return redirect("nominas")
    return render(
        request,
        "negocio/form.html",
        {
            "form": form,
            "titulo": "Editar nómina" if obj else "Nueva nómina",
            "subtitulo": "Salario bruto, IRPF, Seguridad Social y neto",
            "volver": "nominas",
        },
    )


@login_required
@admin_required
@require_POST
def nomina_borrar(request, pk):
    obj = get_object_or_404(Nomina.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Nómina eliminada.")
    return redirect("nominas")


# ---------------------------------------------------------------------------
# Facturas importadas
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def facturas(request):
    qs = _qs(FacturaImportada, request)
    estado = request.GET.get("estado", "")
    if estado:
        qs = qs.filter(estado=estado)
    return render(
        request,
        "negocio/facturas.html",
        _contexto_lista(request, _pagin(request, qs, 20)),
    )


@login_required
@gestor_required
def factura_subir(request):
    org = _org(request)
    form = FacturaImportadaForm(request.POST or None, request.FILES or None, organizacion=org)
    if request.method == "POST" and form.is_valid():
        factura = form.save(commit=False)
        factura.organizacion = org
        factura.save()
        factura.procesar()
        messages.success(request, "Factura subida. Revisa los datos detectados.")
        return redirect("factura_revisar", pk=factura.pk)
    return render(
        request,
        "negocio/factura_subir.html",
        {"form": form},
    )


@login_required
@gestor_required
def factura_revisar(request, pk):
    factura = get_object_or_404(FacturaImportada.all_objects, pk=pk, organizacion=_org(request))
    datos = factura.datos or {}
    base = datos.get("base", "")
    total = datos.get("total", "")
    iva = datos.get("iva_pct", 21)
    comun = {
        "factura": factura.pk,
        "proveedor_nombre": datos.get("proveedor", ""),
        "cif": datos.get("cif", ""),
        "numero": datos.get("numero", ""),
        "fecha": datos.get("fecha", ""),
        "base": base,
        "total": total,
        "iva_pct": iva,
        "descripcion": f"Factura {datos.get('proveedor', '')} {datos.get('numero', '')}".strip(),
    }
    gasto_url = reverse("gasto_nuevo") + "?" + urlencode(comun)
    compra_url = reverse("compra_nuevo") + "?" + urlencode(comun)
    venta_url = reverse("venta_nuevo") + "?" + urlencode({**comun, "tipo": "factura"})
    return render(
        request,
        "negocio/factura_revisar.html",
        {
            "factura": factura,
            "datos": datos,
            "gasto_url": gasto_url,
            "compra_url": compra_url,
            "venta_url": venta_url,
        },
    )


@login_required
@gestor_required
@require_POST
def factura_descartar(request, pk):
    factura = get_object_or_404(FacturaImportada.all_objects, pk=pk, organizacion=_org(request))
    factura.estado = "descartada"
    factura.save(update_fields=["estado", "actualizado"])
    messages.info(request, "Factura descartada.")
    return redirect("facturas")


@login_required
@admin_required
@require_POST
def factura_borrar(request, pk):
    factura = get_object_or_404(FacturaImportada.all_objects, pk=pk, organizacion=_org(request))
    if factura.archivo:
        factura.archivo.delete(save=False)
    factura.delete()
    messages.success(request, "Factura eliminada.")
    return redirect("facturas")


# ---------------------------------------------------------------------------
# Configuración: tiendas y familias
# ---------------------------------------------------------------------------
@login_required
@admin_required
def configuracion(request):
    return render(
        request,
        "negocio/configuracion.html",
        {
            "tiendas_lista": _qs(Tienda, request),
            "familias_lista": _qs(Familia, request),
        },
    )


@login_required
@admin_required
def tienda_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Tienda.all_objects, pk=pk, organizacion=org) if pk else None
    form = TiendaForm(request.POST or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.save()
        messages.success(request, "Tienda guardada.")
        return redirect("configuracion")
    return render(
        request,
        "negocio/form.html",
        {"form": form, "titulo": "Editar tienda" if obj else "Nueva tienda", "volver": "configuracion"},
    )


@login_required
@admin_required
def familia_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Familia.all_objects, pk=pk, organizacion=org) if pk else None
    form = FamiliaForm(request.POST or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.organizacion = org
        obj.save()
        messages.success(request, "Familia guardada.")
        return redirect("configuracion")
    return render(
        request,
        "negocio/form.html",
        {"form": form, "titulo": "Editar familia" if obj else "Nueva familia", "volver": "configuracion"},
    )


# ---------------------------------------------------------------------------
# Exportaciones PDF / Excel
# ---------------------------------------------------------------------------
def _xlsx_bytes(hojas):
    """hojas = [(nombre, headers, rows), ...]"""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    wb.remove(wb.active)
    for nombre, headers, rows in hojas:
        ws = wb.create_sheet(title=nombre[:31])
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="0F172A")
            cell.alignment = Alignment(horizontal="center")
        for row in rows:
            ws.append(row)
        for i, header in enumerate(headers, start=1):
            ancho = max([len(str(header))] + [len(str(r[i - 1])) for r in rows[:200] if i - 1 < len(r)]) + 2
            ws.column_dimensions[get_column_letter(i)].width = min(max(ancho, 10), 40)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _pdf_bytes(titulo, subtitulo, headers, rows, landscape=True, pie=""):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape as landscape_page
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    buffer = io.BytesIO()
    page = landscape_page(A4) if landscape else A4
    doc = SimpleDocTemplate(
        buffer, pagesize=page,
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=titulo,
    )
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#0f172a"), spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#6b7280"), spaceAfter=8)
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7.5, leading=9)
    head = ParagraphStyle("head", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")

    data = [[Paragraph(escape(str(x)), head) for x in headers]]
    for row in rows:
        data.append([Paragraph(escape(str(x)), cell) for x in row])
    tabla = Table(data, repeatRows=1)
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d6d3d1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f5ef")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    def footer(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(12 * mm, 7 * mm, pie or "Bosselli Gestión · documento interno")
        canvas.drawRightString(page[0] - 12 * mm, 7 * mm, f"Página {documento.page}")
        canvas.restoreState()

    story = [Paragraph(escape(titulo), h), Paragraph(escape(subtitulo), sub), Spacer(1, 4), tabla]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _datos_export(request, tipo):
    org = _org(request)
    desde = _fecha(request.GET.get("desde"))
    hasta = _fecha(request.GET.get("hasta"))
    tienda = request.GET.get("tienda", "")
    titulo = "Listado"
    headers = []
    rows = []
    nombre = tipo

    if tipo == "ventas":
        qs = Venta.all_objects.filter(organizacion=org).select_related("tienda", "cliente")
        if desde:
            qs = qs.filter(fecha__gte=desde)
        if hasta:
            qs = qs.filter(fecha__lte=hasta)
        if tienda:
            qs = qs.filter(tienda_id=tienda)
        qs = qs.order_by("-fecha", "-id")
        titulo = "Ventas"
        headers = ["Número", "Fecha", "Tienda", "Cliente", "Tipo", "Base", "IVA", "Total", "Pago", "Estado"]
        rows = [
            [v.numero, v.fecha.strftime("%d/%m/%Y"), v.tienda.nombre, str(v.cliente or "—"),
             v.get_tipo_display(), f"{v.base:.2f}", f"{v.iva_cuota:.2f}", f"{v.total:.2f}",
             v.get_forma_pago_display(), v.get_estado_display()]
            for v in qs
        ]
    elif tipo == "compras":
        qs = Compra.all_objects.filter(organizacion=org).select_related("proveedor")
        if desde:
            qs = qs.filter(fecha__gte=desde)
        if hasta:
            qs = qs.filter(fecha__lte=hasta)
        qs = qs.order_by("-fecha", "-id")
        titulo = "Compras"
        headers = ["Número", "Fecha", "Proveedor", "Base", "IVA", "Total", "Estado", "Recibida"]
        rows = [
            [c.numero, c.fecha.strftime("%d/%m/%Y"), c.proveedor.nombre, f"{c.base:.2f}",
             f"{c.iva_cuota:.2f}", f"{c.total:.2f}", c.get_estado_display(), "Sí" if c.recibida else "No"]
            for c in qs
        ]
    elif tipo == "gastos":
        qs = Gasto.all_objects.filter(organizacion=org).select_related("proveedor", "tienda")
        if desde:
            qs = qs.filter(fecha__gte=desde)
        if hasta:
            qs = qs.filter(fecha__lte=hasta)
        if tienda:
            qs = qs.filter(tienda_id=tienda)
        qs = qs.order_by("-fecha", "-id")
        titulo = "Gastos"
        headers = ["Fecha", "Categoría", "Proveedor", "Descripción", "Base", "IVA", "Total", "Tienda"]
        rows = [
            [g.fecha.strftime("%d/%m/%Y"), g.get_categoria_display(), g.nombre_proveedor,
             g.descripcion, f"{g.base:.2f}", f"{g.iva_cuota:.2f}", f"{g.total:.2f}",
             str(g.tienda or "—")]
            for g in qs
        ]
    elif tipo == "articulos":
        qs = Articulo.all_objects.filter(organizacion=org).select_related("familia", "proveedor").prefetch_related("variantes__stocks")
        titulo = "Artículos"
        headers = ["Referencia", "Artículo", "Familia", "Marca", "Coste", "PVP", "Margen %", "Stock", "Mínimo"]
        rows = [
            [a.referencia, a.nombre, a.familia.nombre, a.marca, f"{a.coste:.2f}",
             f"{a.pvp:.2f}", f"{a.margen:.2f}", a.stock_total, a.stock_minimo]
            for a in qs
        ]
    elif tipo == "stock":
        qs = Stock.all_objects.filter(organizacion=org).select_related("variante__articulo", "tienda")
        if tienda:
            qs = qs.filter(tienda_id=tienda)
        titulo = "Stock por tienda"
        headers = ["Referencia", "Artículo", "Talla", "Color", "Tienda", "Cantidad", "Valor coste"]
        rows = [
            [s.variante.articulo.referencia, s.variante.articulo.nombre, s.variante.talla,
             s.variante.color, s.tienda.nombre, s.cantidad, f"{s.valor_coste:.2f}"]
            for s in qs
        ]
    elif tipo == "clientes":
        qs = Cliente.all_objects.filter(organizacion=org).order_by("nombre", "apellidos")
        titulo = "Clientes"
        headers = ["Nombre", "NIF", "Email", "Teléfono", "Ciudad", "Tipo"]
        rows = [[c.nombre_completo, c.nif, c.email, c.telefono, c.ciudad, c.get_tipo_display()] for c in qs]
    elif tipo == "proveedores":
        qs = Proveedor.all_objects.filter(organizacion=org).order_by("nombre")
        titulo = "Proveedores"
        headers = ["Nombre", "CIF", "Contacto", "Teléfono", "Email"]
        rows = [[p.nombre, p.cif, p.persona_contacto, p.telefono, p.email] for p in qs]
    elif tipo == "nominas":
        qs = Nomina.all_objects.filter(organizacion=org).select_related("empleado")
        anyo = request.GET.get("anyo", "")
        if anyo:
            qs = qs.filter(periodo__year=anyo)
        titulo = "Nóminas"
        headers = ["Periodo", "Empleado", "Bruto", "IRPF", "SS empleado", "Neto", "Estado"]
        rows = [
            [n.periodo.strftime("%m/%Y"), n.empleado.nombre_completo, f"{n.bruto:.2f}",
             f"{n.irpf:.2f}", f"{n.ss_empleado:.2f}", f"{n.neto:.2f}", n.get_estado_display()]
            for n in qs
        ]
    elif tipo == "empleados":
        qs = Empleado.all_objects.filter(organizacion=org).select_related("tienda").order_by("apellidos")
        titulo = "Empleados"
        headers = ["Nombre", "NIF", "Puesto", "Tienda", "Alta", "Salario anual", "Activo"]
        rows = [
            [e.nombre_completo, e.nif, e.puesto, str(e.tienda or "—"),
             e.fecha_alta.strftime("%d/%m/%Y"), f"{e.salario_bruto_anual:.2f}", "Sí" if e.activo else "No"]
            for e in qs
        ]
    else:
        raise Http404("Listado no disponible")
    return titulo, headers, rows


@login_required
@gestor_required
def exportar(request, tipo, fmt):
    titulo, headers, rows = _datos_export(request, tipo)
    fecha = timezone.localdate().strftime("%Y%m%d")
    subtitulo = f"Generado el {timezone.localtime():%d/%m/%Y %H:%M} · {len(rows)} registros"
    if fmt == "xlsx":
        contenido = _xlsx_bytes([(titulo, headers, rows)])
        resp = HttpResponse(
            contenido,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f'attachment; filename="{tipo}_{fecha}.xlsx"'
    elif fmt == "pdf":
        contenido = _pdf_bytes(titulo, subtitulo, headers, rows, landscape=True)
        resp = HttpResponse(contenido, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{tipo}_{fecha}.pdf"'
    else:
        raise Http404
    registrar(request, "exportar", objeto_repr=f"{titulo} ({fmt})")
    return resp


@login_required
@gestor_required
def informes(request):
    return render(request, "negocio/informes.html", {"hoy": timezone.localdate()})


# ---------------------------------------------------------------------------
# PDF de venta y nómina
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def venta_pdf(request, pk):
    venta = get_object_or_404(
        Venta.all_objects.select_related("tienda", "cliente").prefetch_related("lineas"),
        pk=pk, organizacion=_org(request),
    )
    org = venta.organizacion
    headers = ["Concepto", "Cantidad", "Precio", "Dto.", "IVA", "Total"]
    rows = [
        [l.descripcion, l.cantidad, f"{l.precio_unitario:.2f}", f"{l.descuento_pct:.0f}%",
         f"{l.iva_pct:.0f}%", f"{l.total:.2f}"]
        for l in venta.lineas.all()
    ]
    if not rows:
        rows = [["Venta registrada", 1, f"{venta.base:.2f}", "0%", f"{venta.iva_pct:.0f}%", f"{venta.total:.2f}"]]
    rows += [
        ["", "", "", "", "Base imponible", f"{venta.base:.2f}"],
        ["", "", "", "", "IVA", f"{venta.iva_cuota:.2f}"],
        ["", "", "", "", "TOTAL", f"{venta.total:.2f}"],
    ]
    subtitulo = (
        f"{org.nombre} · {venta.tienda.nombre} · {venta.numero} · "
        f"{venta.fecha:%d/%m/%Y} · {venta.get_tipo_display()}"
    )
    if venta.cliente:
        subtitulo += f" · Cliente: {venta.cliente}"
    contenido = _pdf_bytes(
        f"{org.nombre} — {venta.get_tipo_display()}", subtitulo, headers, rows,
        landscape=False,
        pie=f"{org.nombre} · {org.direccion or ''} · {org.telefono or ''}",
    )
    resp = HttpResponse(contenido, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{venta.numero}.pdf"'
    return resp


@login_required
@gestor_required
def nomina_pdf(request, pk):
    nomina = get_object_or_404(
        Nomina.all_objects.select_related("empleado", "empleado__tienda"),
        pk=pk, organizacion=_org(request),
    )
    headers = ["Concepto", "Importe"]
    rows = [
        ["Salario base", f"{nomina.salario_base:.2f}"],
        ["Complementos", f"{nomina.complementos:.2f}"],
        ["Prorrateo pagas extra", f"{nomina.prorrateo_pagas:.2f}"],
        ["Total bruto", f"{nomina.bruto:.2f}"],
        [f"IRPF ({nomina.irpf_pct:.2f}%)", f"-{nomina.irpf:.2f}"],
        ["Seguridad Social empleado", f"-{nomina.ss_empleado:.2f}"],
        ["Otras deducciones", f"-{nomina.otras_deducciones:.2f}"],
        ["NETO A PERCIBIR", f"{nomina.neto:.2f}"],
        ["Seguridad Social empresa", f"{nomina.ss_empresa:.2f}"],
    ]
    subtitulo = f"{nomina.empleado.nombre_completo} · {nomina.periodo:%m/%Y} · {nomina.get_estado_display()}"
    contenido = _pdf_bytes("Recibo de salarios", subtitulo, headers, rows, landscape=False)
    resp = HttpResponse(contenido, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="nomina_{nomina.pk}.pdf"'
    return resp


@login_required
@gestor_required
@require_POST
def venta_email(request, pk):
    venta = get_object_or_404(
        Venta.all_objects.select_related("tienda", "cliente"),
        pk=pk, organizacion=_org(request),
    )
    destino = request.POST.get("email") or (venta.cliente.email if venta.cliente else "")
    if not destino:
        messages.error(request, "Indica un email de destino.")
        return redirect("venta_detalle", pk=venta.pk)
    pdf = venta_pdf(request, pk).content
    asunto = f"{venta.get_tipo_display()} {venta.numero} · Bosselli"
    cuerpo = (
        f"Hola{(' ' + venta.cliente.nombre) if venta.cliente else ''},\n\n"
        f"Adjuntamos el documento de tu compra en Bosselli.\n\n"
        f"Importe: {eur(venta.total)}\nFecha: {venta.fecha:%d/%m/%Y}\n\n"
        f"Gracias por confiar en nosotros.\n\nBosselli · Sastrería y moda clásica desde 1973"
    )
    email = EmailMessage(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [destino])
    email.attach(f"{venta.numero}.pdf", pdf, "application/pdf")
    try:
        email.send()
        registrar(request, "envio_email", objeto=venta, objeto_repr=f"Email a {destino}")
        messages.success(request, f"Documento enviado a {destino}.")
    except Exception as exc:
        messages.error(request, f"No se pudo enviar el email: {exc}")
    return redirect("venta_detalle", pk=venta.pk)


# ---------------------------------------------------------------------------
# Gestoría
# ---------------------------------------------------------------------------
def _periodo_trimestre(anyo, trimestre):
    inicio_mes = (int(trimestre) - 1) * 3 + 1
    fin_mes = inicio_mes + 2
    inicio = date(int(anyo), inicio_mes, 1)
    if fin_mes == 12:
        fin = date(int(anyo), 12, 31)
    else:
        fin = date(int(anyo), fin_mes + 1, 1) - timedelta(days=1)
    return inicio, fin


@login_required
@gestor_required
def gestoria(request):
    hoy = timezone.localdate()
    anyo = request.GET.get("anyo", str(hoy.year))
    trimestre = request.GET.get("trimestre", str((hoy.month - 1) // 3 + 1))
    inicio, fin = _periodo_trimestre(anyo, trimestre)
    org = _org(request)

    ventas = Venta.all_objects.filter(organizacion=org, fecha__range=(inicio, fin)).exclude(estado="anulada")
    compras = Compra.all_objects.filter(organizacion=org, fecha__range=(inicio, fin)).exclude(estado="anulada")
    gastos = Gasto.all_objects.filter(organizacion=org, fecha__range=(inicio, fin))
    nominas = Nomina.all_objects.filter(organizacion=org, periodo__range=(inicio, fin))

    ctx = {
        "anyo": anyo,
        "trimestre": trimestre,
        "inicio": inicio,
        "fin": fin,
        "n_ventas": ventas.count(),
        "n_compras": compras.count(),
        "n_gastos": gastos.count(),
        "n_nominas": nominas.count(),
        "total_ventas": ventas.aggregate(s=Sum("total"))["s"] or 0,
        "total_compras": compras.aggregate(s=Sum("total"))["s"] or 0,
        "total_gastos": gastos.aggregate(s=Sum("total"))["s"] or 0,
        "total_nominas": nominas.aggregate(s=Sum("bruto"))["s"] or 0,
        "n_archivos": sum(
            1 for qs in (ventas, compras, gastos, nominas) for o in qs if getattr(o, "archivo", None)
        ),
    }
    return render(request, "negocio/gestoria.html", ctx)


@login_required
@gestor_required
def gestoria_zip(request):
    org = _org(request)
    anyo = request.GET.get("anyo", str(timezone.localdate().year))
    trimestre = request.GET.get("trimestre", "1")
    inicio, fin = _periodo_trimestre(anyo, trimestre)

    ventas = list(Venta.all_objects.filter(organizacion=org, fecha__range=(inicio, fin)).exclude(estado="anulada").select_related("tienda", "cliente"))
    compras = list(Compra.all_objects.filter(organizacion=org, fecha__range=(inicio, fin)).exclude(estado="anulada").select_related("proveedor"))
    gastos = list(Gasto.all_objects.filter(organizacion=org, fecha__range=(inicio, fin)).select_related("proveedor", "tienda"))
    nominas = list(Nomina.all_objects.filter(organizacion=org, periodo__range=(inicio, fin)).select_related("empleado"))

    hojas = [
        (
            "Ventas",
            ["Número", "Fecha", "Tienda", "Cliente", "Tipo", "Base", "IVA", "Total", "Estado"],
            [[v.numero, v.fecha.strftime("%d/%m/%Y"), v.tienda.nombre, str(v.cliente or ""),
              v.get_tipo_display(), f"{v.base:.2f}", f"{v.iva_cuota:.2f}", f"{v.total:.2f}",
              v.get_estado_display()] for v in ventas],
        ),
        (
            "Compras",
            ["Número", "Fecha", "Proveedor", "Base", "IVA", "Total", "Estado"],
            [[c.numero, c.fecha.strftime("%d/%m/%Y"), c.proveedor.nombre, f"{c.base:.2f}",
              f"{c.iva_cuota:.2f}", f"{c.total:.2f}", c.get_estado_display()] for c in compras],
        ),
        (
            "Gastos",
            ["Fecha", "Categoría", "Proveedor", "Descripción", "Base", "IVA", "Total"],
            [[g.fecha.strftime("%d/%m/%Y"), g.get_categoria_display(), g.nombre_proveedor,
              g.descripcion, f"{g.base:.2f}", f"{g.iva_cuota:.2f}", f"{g.total:.2f}"] for g in gastos],
        ),
        (
            "Nóminas",
            ["Periodo", "Empleado", "Bruto", "IRPF", "SS empleado", "Neto", "Estado"],
            [[n.periodo.strftime("%m/%Y"), n.empleado.nombre_completo, f"{n.bruto:.2f}",
              f"{n.irpf:.2f}", f"{n.ss_empleado:.2f}", f"{n.neto:.2f}", n.get_estado_display()] for n in nominas],
        ),
    ]

    tv = sum((v.total for v in ventas), D("0"))
    tc = sum((c.total for c in compras), D("0"))
    tg = sum((g.total for g in gastos), D("0"))
    tn = sum((n.bruto for n in nominas), D("0"))
    resumen_rows = [
        ["Ventas", len(ventas), f"{tv:.2f}"],
        ["Compras", len(compras), f"{tc:.2f}"],
        ["Gastos", len(gastos), f"{tg:.2f}"],
        ["Nóminas (bruto)", len(nominas), f"{tn:.2f}"],
        ["Resultado estimado", "", f"{tv - tc - tg - tn:.2f}"],
    ]
    hojas.append(("Resumen", ["Concepto", "Nº", "Importe"], resumen_rows))

    excel = _xlsx_bytes(hojas)
    pdf = _pdf_bytes(
        f"Resumen trimestral {trimestre}T {anyo}",
        f"{org.nombre} · {inicio:%d/%m/%Y} a {fin:%d/%m/%Y}",
        ["Concepto", "Nº", "Importe"], resumen_rows, landscape=False,
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"Resumen_{anyo}_T{trimestre}.xlsx", excel)
        zf.writestr(f"Resumen_{anyo}_T{trimestre}.pdf", pdf)
        for carpeta, objetos in (
            ("Ventas", ventas), ("Compras", compras), ("Gastos", gastos), ("Nominas", nominas)
        ):
            for obj in objetos:
                archivo = getattr(obj, "archivo", None)
                if archivo and archivo.name:
                    try:
                        with archivo.open("rb") as fh:
                            nombre = os.path.basename(archivo.name)
                            zf.writestr(f"{carpeta}/{obj.pk}_{nombre}", fh.read())
                    except Exception:
                        continue
    contenido = buffer.getvalue()

    destino = request.GET.get("enviar")
    if destino == "1":
        from core.models import Ajuste

        ajuste = Ajuste.obtener()
        email_destino = request.GET.get("email") or ajuste.email_gestoria or getattr(org, "email", "")
        if not email_destino:
            messages.error(request, "No hay email de gestoría configurado.")
            return redirect("gestoria")
        email = EmailMessage(
            f"Documentación {trimestre}T {anyo} · {org.nombre}",
            f"Adjuntamos la documentación del trimestre.\n\n{org.nombre}",
            settings.DEFAULT_FROM_EMAIL,
            [email_destino],
        )
        email.attach(f"Gestoria_{anyo}_T{trimestre}.zip", contenido, "application/zip")
        try:
            email.send()
            registrar(request, "envio_email", objeto_repr=f"Gestión {trimestre}T {anyo} a {email_destino}")
            messages.success(request, f"Paquete enviado a {email_destino}.")
        except Exception as exc:
            messages.error(request, f"No se pudo enviar: {exc}")
        return redirect("gestoria")

    resp = HttpResponse(contenido, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="Gestoria_{anyo}_T{trimestre}.zip"'
    registrar(request, "exportar", objeto_repr=f"Paquete gestoría {trimestre}T {anyo}")
    return resp

# ---------------------------------------------------------------------------
# Backup diario (datos completos)
# ---------------------------------------------------------------------------
@login_required
@admin_required
def backup(request):
    """Pantalla de backup: descargar o enviar toda la base de datos."""
    from core.models import Ajuste

    ajuste = Ajuste.obtener()
    emails = [e.strip() for e in (ajuste.emails_backup or "").split(",") if e.strip()]
    return render(request, "negocio/backup.html", {"emails": emails, "ajuste": ajuste})


def _generar_backup_zip(org):
    """Genera un ZIP con dump JSON + Excel de todos los datos de la organización."""
    import io
    import json
    import zipfile
    from datetime import datetime
    from django.core import serializers

    from .models import (
        Articulo, Cliente, Compra, Empleado, FacturaImportada, Familia,
        Gasto, LineaCompra, LineaVenta, Nomina, Proveedor, Stock,
        Tienda, Variante, Venta,
    )
    from core.models import Organizacion

    buffer = io.BytesIO()
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        modelos = [
            Organizacion, Tienda, Familia, Proveedor, Cliente, Articulo,
            Variante, Stock, Venta, LineaVenta, Compra, LineaCompra,
            Gasto, Empleado, Nomina, FacturaImportada,
        ]
        for modelo in modelos:
            try:
                if hasattr(modelo, "all_objects"):
                    qs = modelo.all_objects.filter(organizacion=org)
                else:
                    qs = modelo.objects.all()
                    if hasattr(modelo, "organizacion"):
                        qs = qs.filter(organizacion=org)
            except Exception:
                continue
            try:
                data = serializers.serialize("json", qs, indent=2, use_natural_foreign_keys=True)
                nombre = modelo.__name__.lower()
                zf.writestr(f"json/{nombre}.json", data)
            except Exception:
                continue

        try:
            todo = []
            for modelo in modelos:
                try:
                    if hasattr(modelo, "all_objects"):
                        qs = modelo.all_objects.filter(organizacion=org)
                    else:
                        qs = modelo.objects.all()
                        if hasattr(modelo, "organizacion"):
                            qs = qs.filter(organizacion=org)
                    todo.extend(json.loads(serializers.serialize("json", qs, use_natural_foreign_keys=True)))
                except Exception:
                    continue
            zf.writestr("json/backup_completo.json", json.dumps(todo, indent=2, ensure_ascii=False))
        except Exception:
            pass

        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill

        def hoja_excel(wb, nombre, headers, rows):
            ws = wb.create_sheet(title=nombre[:31])
            ws.append(headers)
            for cell in ws[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="0F172A")
            for row in rows:
                ws.append(row)
            for i in range(1, len(headers) + 1):
                ws.column_dimensions[chr(64 + i) if i < 27 else "A"].width = 16
            ws.freeze_panes = "A2"
            return ws

        wb = Workbook()
        wb.remove(wb.active)

        ventas = Venta.all_objects.filter(organizacion=org).select_related("tienda", "cliente")
        hoja_excel(wb, "Ventas", ["Numero", "Fecha", "Tienda", "Cliente", "Tipo", "Base", "IVA", "Total", "Estado"],
                   [[v.numero, v.fecha.isoformat(), v.tienda.nombre, str(v.cliente or ""), v.get_tipo_display(),
                     float(v.base), float(v.iva_cuota), float(v.total), v.get_estado_display()] for v in ventas])

        compras = Compra.all_objects.filter(organizacion=org).select_related("proveedor")
        hoja_excel(wb, "Compras", ["Numero", "Fecha", "Proveedor", "Base", "IVA", "Total", "Estado"],
                   [[c.numero, c.fecha.isoformat(), c.proveedor.nombre, float(c.base), float(c.iva_cuota),
                     float(c.total), c.get_estado_display()] for c in compras])

        gastos = Gasto.all_objects.filter(organizacion=org)
        hoja_excel(wb, "Gastos", ["Fecha", "Categoria", "Descripcion", "Base", "IVA", "Total"],
                   [[g.fecha.isoformat(), g.get_categoria_display(), g.descripcion, float(g.base),
                     float(g.iva_cuota), float(g.total)] for g in gastos])

        arts = Articulo.all_objects.filter(organizacion=org)
        hoja_excel(wb, "Articulos", ["Referencia", "Nombre", "Familia", "Coste", "PVP", "Stock", "Minimo"],
                   [[a.referencia, a.nombre, a.familia.nombre, float(a.coste), float(a.pvp),
                     a.stock_total, a.stock_minimo] for a in arts])

        cls = Cliente.all_objects.filter(organizacion=org)
        hoja_excel(wb, "Clientes", ["Nombre", "Apellidos", "NIF", "Email", "Telefono", "Ciudad"],
                   [[c.nombre, c.apellidos, c.nif, c.email, c.telefono, c.ciudad] for c in cls])

        emps = Empleado.all_objects.filter(organizacion=org)
        hoja_excel(wb, "Empleados", ["Nombre", "Apellidos", "NIF", "Puesto", "Salario anual", "Activo"],
                   [[e.nombre, e.apellidos, e.nif, e.puesto, float(e.salario_bruto_anual), e.activo] for e in emps])

        noms = Nomina.all_objects.filter(organizacion=org)
        hoja_excel(wb, "Nominas", ["Periodo", "Empleado", "Bruto", "IRPF", "SS emp", "Neto", "Estado"],
                   [[n.periodo.isoformat(), n.empleado.nombre_completo, float(n.bruto), float(n.irpf),
                     float(n.ss_empleado), float(n.neto), n.get_estado_display()] for n in noms])

        excel_buf = io.BytesIO()
        wb.save(excel_buf)
        zf.writestr(f"excel/backup_{fecha}.xlsx", excel_buf.getvalue())

        zf.writestr("LEEME.txt", (
            f"Backup de Bosselli Gestion\n"
            f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"Organizacion: {org.nombre}\n\n"
            f"Contenido:\n"
            f"- json/: dump de cada modelo en formato JSON (re-importable con loaddata).\n"
            f"- json/backup_completo.json: todos los datos en un solo archivo.\n"
            f"- excel/: resumen en Excel para consulta humana.\n\n"
            f"Para restaurar: python manage.py loaddata json/backup_completo.json\n"
        ))
    return buffer.getvalue(), fecha


@login_required
@admin_required
def backup_descargar(request):
    org = request.organizacion
    contenido, fecha = _generar_backup_zip(org)
    resp = HttpResponse(contenido, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="backup_bosselli_{fecha}.zip"'
    registrar(request, "exportar", objeto_repr=f"Backup descargado {fecha}")
    return resp


@login_required
@admin_required
def backup_email(request):
    from core.models import Ajuste
    from django.core.mail import EmailMessage

    org = request.organizacion
    ajuste = Ajuste.obtener()
    emails = [e.strip() for e in (ajuste.emails_backup or "").split(",") if e.strip()]
    extra = request.POST.get("emails", "").strip()
    if extra:
        emails = [e.strip() for e in extra.split(",") if e.strip()]
    if not emails:
        messages.error(request, "No hay emails configurados para el backup. Añadelos en Ajustes (admin).")
        return redirect("backup")
    contenido, fecha = _generar_backup_zip(org)
    email = EmailMessage(
        f"Backup Bosselli Gestion - {fecha}",
        f"Adjuntamos el backup completo de los datos de Bosselli.\n\n"
        f"Fecha: {fecha}\nOrganizacion: {org.nombre}\n\n"
        f"Para restaurar: python manage.py loaddata json/backup_completo.json\n",
        settings.DEFAULT_FROM_EMAIL,
        emails,
    )
    email.attach(f"backup_bosselli_{fecha}.zip", contenido, "application/zip")
    try:
        email.send()
        registrar(request, "envio_email", objeto_repr=f"Backup enviado a {', '.join(emails)}")
        messages.success(request, f"Backup enviado a {', '.join(emails)}.")
    except Exception as exc:
        messages.error(request, f"No se pudo enviar: {exc}")
    return redirect("backup")


# ---------------------------------------------------------------------------
# Notificaciones
# ---------------------------------------------------------------------------
@login_required
def notificaciones(request):
    org = request.organizacion
    from .models import Articulo
    from core.models import Ajuste

    ajuste = Ajuste.obtener()

    articulos_bajo = [
        a for a in Articulo.all_objects.filter(organizacion=org, activo=True).prefetch_related("variantes__stocks")
        if a.bajo_minimo
    ]

    facturas_pend = FacturaImportada.all_objects.filter(organizacion=org, estado="pendiente")
    compras_pend = Compra.all_objects.filter(organizacion=org, estado="pendiente")
    nominas_borr = Nomina.all_objects.filter(organizacion=org, estado="borrador")

    total_alertas = len(articulos_bajo) + facturas_pend.count() + compras_pend.count() + nominas_borr.count()

    if request.method == "POST" and request.POST.get("enviar_alerta") == "1":
        from django.core.mail import EmailMessage
        emails = [ajuste.email_notificaciones] if ajuste.email_notificaciones else []
        extra = request.POST.get("emails", "").strip()
        if extra:
            emails = [e.strip() for e in extra.split(",") if e.strip()]
        if not emails:
            messages.error(request, "No hay email de notificaciones configurado. AÃ±adelo en Ajustes (admin).")
        elif not articulos_bajo:
            messages.info(request, "No hay artÃ­culos con stock bajo. No se envÃ­a alerta.")
        else:
            cuerpo = "Alerta de stock bajo - Bosselli GestiÃ³n\n\n"
            cuerpo += "Los siguientes artÃ­culos estÃ¡n por debajo del stock mÃ­nimo:\n\n"
            for a in articulos_bajo:
                cuerpo += f"  - {a.referencia} {a.nombre}: {a.stock_total} unidades (mÃ­nimo: {a.stock_minimo})\n"
            cuerpo += f"\nTotal de artÃ­culos afectados: {len(articulos_bajo)}\n"
            cuerpo += "\nBosselli Â· SastrerÃ­a y moda clÃ¡sica desde 1973"
            email = EmailMessage(
                f"Alerta stock bajo - {len(articulos_bajo)} artÃ­culos",
                cuerpo,
                settings.DEFAULT_FROM_EMAIL,
                emails,
            )
            try:
                email.send()
                registrar(request, "envio_aviso", objeto_repr=f"Alerta stock bajo a {', '.join(emails)}")
                messages.success(request, f"Alerta enviada a {', '.join(emails)}.")
            except Exception as exc:
                messages.error(request, f"No se pudo enviar: {exc}")
        return redirect("notificaciones")

    return render(request, "negocio/notificaciones.html", {
        "articulos_bajo": articulos_bajo,
        "facturas_pend": facturas_pend,
        "compras_pend": compras_pend,
        "nominas_borr": nominas_borr,
        "total_alertas": total_alertas,
        "ajuste": ajuste,
    })

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum

from .forms import (
    ArqueoCajaForm, DevolucionForm, EventoForm, InventarioFisicoForm,
    LineaDevolucionFormSet, MedidaClienteForm,
)
from .models import (
    ArqueoCaja, Devolucion, Evento, InventarioFisico, LineaDevolucion,
    LineaInventario, MedidaCliente, Stock, Variante,
)


# ---------------------------------------------------------------------------
# Arqueo de caja
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def arqueos(request):
    qs = ArqueoCaja.all_objects.filter(organizacion=_org(request)).select_related("tienda")
    qs = qs.order_by("-fecha", "-id")
    return render(request, "negocio/arqueos.html", _contexto_lista(request, _pagin(request, qs, 20)))


@login_required
@gestor_required
def arqueo_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(ArqueoCaja.all_objects, pk=pk, organizacion=org) if pk else None
    initial = {}
    if obj is None:
        tienda = _qs(Tienda, request).filter(activa=True).first()
        if tienda:
            initial["tienda"] = tienda
        initial["fecha"] = timezone.localdate()
    form = ArqueoCajaForm(request.POST or None, instance=obj, initial=initial, organizacion=org)
    if request.method == "POST" and form.is_valid():
        arqueo = form.save(commit=False)
        arqueo.organizacion = org
        arqueo.usuario = request.user
        arqueo.calcular_esperado()
        arqueo.save()
        messages.success(request, "Arqueo guardado.")
        return redirect("arqueos")
    # Calcular esperado para mostrar
    esperado = None
    if form.instance and form.instance.tienda_id:
        try:
            a = form.instance
            a.organizacion = org
            a.calcular_esperado()
            esperado = a
        except Exception:
            pass
    return render(request, "negocio/arqueo_form.html", {"form": form, "obj": obj, "esperado": esperado})


@login_required
@admin_required
@require_POST
def arqueo_borrar(request, pk):
    obj = get_object_or_404(ArqueoCaja.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Arqueo eliminado.")
    return redirect("arqueos")


# ---------------------------------------------------------------------------
# Devoluciones
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def devoluciones(request):
    qs = Devolucion.all_objects.filter(organizacion=_org(request)).select_related("venta", "venta__cliente")
    qs = qs.order_by("-fecha", "-id")
    return render(request, "negocio/devoluciones.html", _contexto_lista(request, _pagin(request, qs, 20)))


@login_required
@gestor_required
def devolucion_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Devolucion.all_objects, pk=pk, organizacion=org) if pk else None
    initial = {}
    if obj is None and request.GET.get("venta"):
        initial["venta"] = request.GET.get("venta")
    form = DevolucionForm(request.POST or None, request.FILES or None, instance=obj, initial=initial, organizacion=org)
    formset = LineaDevolucionFormSet(request.POST or None, instance=obj or Devolucion(), prefix="lineas")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        dev = form.save(commit=False)
        dev.organizacion = org
        dev.save()
        formset.instance = dev
        for linea in formset.save(commit=False):
            linea.organizacion = org
            linea.devolucion = dev
            linea.save()
        for borrada in formset.deleted_objects:
            borrada.delete()
        dev.total = dev.total_lineas
        dev.save(update_fields=["total"])
        # Re-entrar stock si se procesa
        if dev.estado == "procesada":
            for linea in dev.lineas.all():
                if linea.variante_id:
                    mover_stock(linea.variante, dev.venta.tienda, linea.cantidad, "devolucion",
                                motivo=f"Devolución {dev.pk}", referencia=dev.venta.numero,
                                usuario=request.user, organizacion=org)
        messages.success(request, "Devolución guardada.")
        return redirect("devoluciones")
    return render(request, "negocio/devolucion_form.html", {"form": form, "formset": formset, "obj": obj})


@login_required
@admin_required
@require_POST
def devolucion_borrar(request, pk):
    obj = get_object_or_404(Devolucion.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Devolución eliminada.")
    return redirect("devoluciones")


# ---------------------------------------------------------------------------
# Inventario físico
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def inventarios(request):
    qs = InventarioFisico.all_objects.filter(organizacion=_org(request)).select_related("tienda")
    qs = qs.order_by("-fecha", "-id")
    return render(request, "negocio/inventarios.html", _contexto_lista(request, _pagin(request, qs, 20)))


@login_required
@gestor_required
def inventario_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(InventarioFisico.all_objects, pk=pk, organizacion=org) if pk else None
    if obj is None and request.method == "GET":
        # Crear nuevo inventario con líneas pre-rellenadas
        tienda_id = request.GET.get("tienda")
        tienda = None
        if tienda_id:
            tienda = _qs(Tienda, request).filter(pk=tienda_id).first()
        if tienda is None:
            tienda = _qs(Tienda, request).filter(activa=True).first()
        if tienda:
            inv = InventarioFisico.all_objects.create(organizacion=org, tienda=tienda, usuario=request.user)
            # Pre-rellenar líneas con stock actual
            from .models import Variante, Stock
            variantes = Variante.all_objects.filter(organizacion=org, activa=True).select_related("articulo")
            for v in variantes:
                stock = Stock.all_objects.filter(organizacion=org, variante=v, tienda=tienda).first()
                LineaInventario.all_objects.create(
                    organizacion=org, inventario=inv, variante=v,
                    cantidad_sistema=stock.cantidad if stock else 0,
                    cantidad_contada=stock.cantidad if stock else 0,
                )
            messages.success(request, "Inventario creado. Cuenta las unidades y ajusta.")
            return redirect("inventario_editar", pk=inv.pk)
    form = InventarioFisicoForm(request.POST or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        inv = form.save(commit=False)
        inv.organizacion = org
        inv.usuario = request.user
        inv.save()
        messages.success(request, "Inventario guardado.")
        return redirect("inventarios")
    # Líneas de inventario
    lineas = []
    if obj:
        lineas = LineaInventario.all_objects.filter(organizacion=org, inventario=obj).select_related("variante__articulo")
    return render(request, "negocio/inventario_form.html", {"form": form, "obj": obj, "lineas": lineas})


@login_required
@gestor_required
def inventario_contar(request, pk):
    org = _org(request)
    inv = get_object_or_404(InventarioFisico.all_objects, pk=pk, organizacion=org)
    if request.method == "POST":
        for linea in inv.lineas.all():
            campo = f"contada_{linea.pk}"
            if campo in request.POST:
                try:
                    linea.cantidad_contada = int(request.POST[campo])
                    linea.save(update_fields=["cantidad_contada", "actualizado"])
                except ValueError:
                    pass
        messages.success(request, "Conteo guardado.")
        return redirect("inventario_editar", pk=inv.pk)
    return redirect("inventario_editar", pk=inv.pk)


@login_required
@gestor_required
@require_POST
def inventario_completar(request, pk):
    org = _org(request)
    inv = get_object_or_404(InventarioFisico.all_objects, pk=pk, organizacion=org)
    # Ajustar stock según diferencias
    for linea in inv.lineas.all():
        diff = linea.diferencia
        if diff != 0:
            mover_stock(linea.variante, inv.tienda, diff, "ajuste",
                        motivo=f"Inventario físico {inv.pk}", referencia=f"INV-{inv.pk}",
                        usuario=request.user, organizacion=org)
    inv.estado = "completado"
    inv.completado = timezone.now()
    inv.save(update_fields=["estado", "completado", "actualizado"])
    messages.success(request, "Inventario completado. Stock ajustado.")
    return redirect("inventarios")


@login_required
@admin_required
@require_POST
def inventario_borrar(request, pk):
    obj = get_object_or_404(InventarioFisico.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Inventario eliminado.")
    return redirect("inventarios")


# ---------------------------------------------------------------------------
# Medidas de cliente
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def medidas_cliente(request, cliente_pk):
    org = _org(request)
    cliente = get_object_or_404(Cliente.all_objects, pk=cliente_pk, organizacion=org)
    medidas = MedidaCliente.all_objects.filter(organizacion=org, cliente=cliente).order_by("-fecha")
    return render(request, "negocio/medidas_cliente.html", {"cliente": cliente, "medidas": medidas})


@login_required
@gestor_required
def medida_form(request, cliente_pk, pk=None):
    org = _org(request)
    cliente = get_object_or_404(Cliente.all_objects, pk=cliente_pk, organizacion=org)
    obj = get_object_or_404(MedidaCliente.all_objects, pk=pk, organizacion=org) if pk else None
    initial = {"cliente": cliente} if not obj else {}
    form = MedidaClienteForm(request.POST or None, instance=obj, initial=initial, organizacion=org)
    if request.method == "POST" and form.is_valid():
        m = form.save(commit=False)
        m.organizacion = org
        m.cliente = cliente
        m.save()
        messages.success(request, "Medidas guardadas.")
        return redirect("medidas_cliente", cliente_pk=cliente.pk)
    return render(request, "negocio/form.html", {"form": form, "titulo": "Nueva medida" if not obj else "Editar medida", "subtitulo": str(cliente), "volver": "medidas_cliente", "volver_pk": cliente.pk})


# ---------------------------------------------------------------------------
# Eventos / calendario
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def eventos(request):
    qs = Evento.all_objects.filter(organizacion=_org(request)).select_related("tienda")
    qs = qs.order_by("fecha")
    return render(request, "negocio/eventos.html", _contexto_lista(request, _pagin(request, qs, 30)))


@login_required
@gestor_required
def evento_form(request, pk=None):
    org = _org(request)
    obj = get_object_or_404(Evento.all_objects, pk=pk, organizacion=org) if pk else None
    form = EventoForm(request.POST or None, instance=obj, organizacion=org)
    if request.method == "POST" and form.is_valid():
        e = form.save(commit=False)
        e.organizacion = org
        e.save()
        messages.success(request, "Evento guardado.")
        return redirect("eventos")
    return render(request, "negocio/form.html", {"form": form, "titulo": "Nuevo evento" if not obj else "Editar evento", "volver": "eventos"})


@login_required
@admin_required
@require_POST
def evento_borrar(request, pk):
    obj = get_object_or_404(Evento.all_objects, pk=pk, organizacion=_org(request))
    obj.delete()
    messages.success(request, "Evento eliminado.")
    return redirect("eventos")


# ---------------------------------------------------------------------------
# Etiquetas de precio con código de barras
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def etiquetas(request):
    org = _org(request)
    variantes = Variante.all_objects.filter(organizacion=org, activa=True).select_related("articulo")
    if request.method == "POST":
        seleccionados = request.POST.getlist("variante")
        cantidad = int(request.POST.get("cantidad", 1) or 1)
        if not seleccionados:
            messages.error(request, "Selecciona al menos una variante.")
            return redirect("etiquetas")
        # Generar PDF
        from reportlab.lib.pagesizes import mm
        from reportlab.lib.units import mm as MM
        from reportlab.pdfgen import canvas
        from reportlab.graphics.barcode import code128
        import io
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(50 * MM, 30 * MM))
        for vid in seleccionados:
            v = Variante.all_objects.get(pk=vid, organizacion=org)
            for _ in range(cantidad):
                # Etiqueta 50x30mm
                c.setFont("Helvetica-Bold", 8)
                c.drawString(2 * MM, 26 * MM, v.articulo.nombre[:28])
                c.setFont("Helvetica", 7)
                c.drawString(2 * MM, 22 * MM, f"Talla: {v.talla}  Color: {v.color}"[:28])
                c.drawString(2 * MM, 18 * MM, f"Ref: {v.articulo.referencia}")
                c.setFont("Helvetica-Bold", 10)
                c.drawString(2 * MM, 13 * MM, f"{v.articulo.pvp:.2f} EUR")
                # Código de barras
                barcode = code128.Code128(v.codigo_barras or v.articulo.referencia, barHeight=8 * MM, barWidth=0.3 * MM)
                barcode.drawOn(c, 2 * MM, 3 * MM)
                c.showPage()
        c.save()
        resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = 'attachment; filename="etiquetas.pdf"'
        registrar(request, "exportar", objeto_repr="Etiquetas de precio")
        return resp
    return render(request, "negocio/etiquetas.html", {"variantes": variantes})


# ---------------------------------------------------------------------------
# Comparativa entre tiendas
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def comparativa(request):
    org = _org(request)
    tiendas = _qs(Tienda, request).filter(activa=True)
    anyo = int(request.GET.get("anyo", timezone.localdate().year))
    datos = []
    for t in tiendas:
        ventas = Venta.all_objects.filter(organizacion=org, tienda=t, fecha__year=anyo).exclude(estado="anulada")
        gastos = Gasto.all_objects.filter(organizacion=org, tienda=t, fecha__year=anyo)
        compras = Compra.all_objects.filter(organizacion=org, fecha__year=anyo).exclude(estado="anulada")
        stock = Stock.all_objects.filter(organizacion=org, tienda=t)
        datos.append({
            "tienda": t,
            "n_ventas": ventas.count(),
            "total_ventas": ventas.aggregate(s=Sum("total"))["s"] or 0,
            "total_gastos": gastos.aggregate(s=Sum("total"))["s"] or 0,
            "n_gastos": gastos.count(),
            "unidades_stock": stock.aggregate(s=Sum("cantidad"))["s"] or 0,
            "valor_stock": sum(s.cantidad * s.variante.articulo.coste for s in stock),
        })
    return render(request, "negocio/comparativa.html", {"datos": datos, "anyo": anyo, "tiendas": tiendas})


# ---------------------------------------------------------------------------
# Reportes avanzados
# ---------------------------------------------------------------------------
@login_required
@gestor_required
def reportes_avanzados(request):
    org = _org(request)
    anyo = int(request.GET.get("anyo", timezone.localdate().year))
    mes = request.GET.get("mes", "")
    # Ventas por familia
    from django.db.models import Count
    ventas_lineas = LineaVenta.all_objects.filter(organizacion=org)
    if anyo:
        ventas_lineas = ventas_lineas.filter(venta__fecha__year=anyo)
    if mes:
        ventas_lineas = ventas_lineas.filter(venta__fecha__month=int(mes))
    por_familia = list(
        ventas_lineas.values("articulo__familia__nombre")
        .annotate(cantidad=Sum("cantidad"), total=Sum("precio_unitario"), n=Count("id"))
        .order_by("-total")
    )
    # Top artículos
    top = list(
        ventas_lineas.values("descripcion")
        .annotate(cantidad=Sum("cantidad"), total=Sum("precio_unitario"))
        .order_by("-cantidad")[:15]
    )
    # Margen por familia
    margen_familia = []
    for f in por_familia:
        fam = f["articulo__familia__nombre"]
        arts = Articulo.all_objects.filter(organizacion=org, familia__nombre=fam)
        coste = sum(a.coste * a.stock_total for a in arts)
        pvp = sum(a.pvp * a.stock_total for a in arts)
        margen_familia.append({"familia": fam, "coste": coste, "pvp": pvp, "margen": (pvp - coste)})
    # Ventas por hora
    from django.db.models.functions import ExtractHour
    por_hora = list(
        Venta.all_objects.filter(organizacion=org, fecha__year=anyo)
        .exclude(estado="anulada")
        .annotate(hora=ExtractHour("creado"))
        .values("hora")
        .annotate(n=Count("id"), total=Sum("total"))
        .order_by("hora")
    )
    return render(request, "negocio/reportes_avanzados.html", {
        "anyo": anyo, "mes": mes,
        "por_familia": por_familia,
        "top": top,
        "margen_familia": margen_familia,
        "por_hora": por_hora,
    })