from django.contrib.contenttypes.models import ContentType

from .models import Auditoria, get_audit_context


def registrar(request, accion, objeto=None, cambios=None, objeto_repr=None):
    """Registra una acción que no pasa por señales (exportar, email, importar...)."""
    ctx = get_audit_context() or {}
    user = getattr(request, "user", None)
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    org = getattr(request, "organizacion", None)
    if org is None and objeto is not None:
        org = getattr(objeto, "organizacion", None)
    ct = None
    oid = ""
    if objeto is not None:
        ct = ContentType.objects.get_for_model(type(objeto))
        oid = str(getattr(objeto, "pk", "") or "")
        if not objeto_repr:
            objeto_repr = str(objeto)
    try:
        Auditoria.objects.create(
            organizacion=org,
            usuario=user,
            usuario_nombre=getattr(user, "username", "") if user else "",
            accion=accion,
            content_type=ct,
            object_id=oid,
            objeto_repr=(objeto_repr or "")[:255],
            cambios=cambios or {},
            ip=ctx.get("ip"),
            user_agent=ctx.get("user_agent", ""),
            ruta=ctx.get("ruta", ""),
            metodo=ctx.get("metodo", ""),
        )
    except Exception:
        pass
