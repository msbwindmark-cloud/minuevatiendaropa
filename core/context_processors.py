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
    try:
        from negocio.models import FacturaImportada, Tienda

        tiendas = list(Tienda.objects.filter(activa=True))
        if org is not None:
            facturas_pendientes = FacturaImportada.all_objects.filter(
                organizacion=org, estado="pendiente"
            ).count()
    except Exception:
        tiendas = []
    return {
        "organizacion": org,
        "perfil": perfil,
        "ajustes": ajustes,
        "tiendas": tiendas,
        "facturas_pendientes": facturas_pendientes,
        "es_superuser": bool(getattr(request.user, "is_superuser", False)),
    }
