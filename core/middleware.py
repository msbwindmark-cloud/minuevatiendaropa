from .models import set_current_org, set_audit_context, _org_context, _audit_context


class TenantMiddleware:
    """Asigna request.organizacion y el contexto multi-tenant."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        org = None
        perfil = None
        user = getattr(request, "user", None)

        if user is not None and user.is_authenticated:
            perfil = getattr(user, "perfil", None)
            if perfil is not None:
                org = perfil.organizacion

        if org is None and user is not None and user.is_authenticated:
            # Superusuario sin perfil: trabaja sobre la primera organización.
            from .models import Organizacion

            try:
                org = Organizacion.objects.order_by("id").first()
            except Exception:
                org = None

        request.perfil = perfil
        request.organizacion = org
        token = set_current_org(org)
        try:
            return self.get_response(request)
        finally:
            _org_context.reset(token)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class AuditoriaMiddleware:
    """Guarda en un contextvar quién hace cada petición, para las señales."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ctx = {
            "user": getattr(request, "user", None),
            "ip": _client_ip(request),
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            "ruta": request.path[:500],
            "metodo": request.method,
            "organizacion": getattr(request, "organizacion", None),
        }
        token = set_audit_context(ctx)
        try:
            return self.get_response(request)
        finally:
            _audit_context.reset(token)
