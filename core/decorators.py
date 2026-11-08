from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def _perfil(request):
    return getattr(request, "perfil", None)


def gestor_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect("login")
        perfil = _perfil(request)
        if user.is_superuser or (perfil and perfil.es_gestor):
            return view(request, *args, **kwargs)
        messages.error(request, "No tienes permisos para esa sección.")
        return redirect("dashboard")

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect("login")
        perfil = _perfil(request)
        if user.is_superuser or (perfil and perfil.es_admin):
            return view(request, *args, **kwargs)
        messages.error(request, "Solo un administrador puede realizar esa acción.")
        return redirect("dashboard")

    return wrapper
