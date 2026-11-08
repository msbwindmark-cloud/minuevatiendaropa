# ---------------------------------------------------------------------------
# Notificaciones
# ---------------------------------------------------------------------------
@login_required
def notificaciones(request):
    org = request.organizacion
    from .models import Articulo
    from core.models import Ajuste

    ajuste = Ajuste.obtener()

    # Stock bajo
    articulos_bajo = [
        a for a in Articulo.all_objects.filter(organizacion=org, activo=True).prefetch_related("variantes__stocks")
        if a.bajo_minimo
    ]

    # Facturas pendientes
    facturas_pend = FacturaImportada.all_objects.filter(organizacion=org, estado="pendiente")

    # Compras pendientes de pago
    compras_pend = Compra.all_objects.filter(organizacion=org, estado="pendiente")

    # Nóminas en borrador
    nominas_borr = Nomina.all_objects.filter(organizacion=org, estado="borrador")

    total_alertas = len(articulos_bajo) + facturas_pend.count() + compras_pend.count() + nominas_borr.count()

    # Enviar email de alerta si se solicita
    if request.method == "POST" and request.POST.get("enviar_alerta") == "1":
        from django.core.mail import EmailMessage
        emails = [ajuste.email_notificaciones] if ajuste.email_notificaciones else []
        extra = request.POST.get("emails", "").strip()
        if extra:
            emails = [e.strip() for e in extra.split(",") if e.strip()]
        if not emails:
            messages.error(request, "No hay email de notificaciones configurado. Añádelo en Ajustes (admin).")
        elif not articulos_bajo:
            messages.info(request, "No hay artículos con stock bajo. No se envía alerta.")
        else:
            cuerpo = "Alerta de stock bajo - Bosselli Gestión\n\n"
            cuerpo += "Los siguientes artículos están por debajo del stock mínimo:\n\n"
            for a in articulos_bajo:
                cuerpo += f"  - {a.referencia} {a.nombre}: {a.stock_total} unidades (mínimo: {a.stock_minimo})\n"
            cuerpo += f"\nTotal de artículos afectados: {len(articulos_bajo)}\n"
            cuerpo += "\nBosselli · Sastrería y moda clásica desde 1973"
            email = EmailMessage(
                f"Alerta stock bajo - {len(articulos_bajo)} artículos",
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