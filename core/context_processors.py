from .models import Ajuste


def organizacion(request):
    org = getattr(request, "organizacion", None)
    perfil = getattr(request, "perfil", None)
    try:
        ajustes = Ajuste.obtener()
    except Exception:
        ajustes = None
    tiendas = []
    facturas_pendientes = 0
    articulos_bajo = 0
    try:
        from negocio.models import Articulo, FacturaImportada, Tienda

        tiendas = list(Tienda.objects.filter(activa=True))
        if org is not None:
            facturas_pendientes = FacturaImportada.all_objects.filter(
                organizacion=org, estado="pendiente"
            ).count()
            articulos_bajo = sum(
                1 for a in Articulo.all_objects.filter(organizacion=org, activo=True)
                if a.bajo_minimo
            )
    except Exception:
        tiendas = []
    return {
        "organizacion": org,
        "perfil": perfil,
        "ajustes": ajustes,
        "tiendas": tiendas,
        "facturas_pendientes": facturas_pendientes,
        "articulos_bajo": articulos_bajo,
        "total_alertas": facturas_pendientes + articulos_bajo,
        "es_superuser": bool(getattr(request.user, "is_superuser", False)),
    }
