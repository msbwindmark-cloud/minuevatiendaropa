import json
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .decorators import gestor_required
from .forms import LoginForm, PasswordChangeBootstrapForm
from .models import Auditoria, Organizacion


class LoginView(DjangoLoginView):
    template_name = "core/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def perfil(request):
    if request.method == "POST":
        form = PasswordChangeBootstrapForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Contraseña actualizada correctamente.")
            return redirect("perfil")
        messages.error(request, "Revisa los datos: la contraseña no se ha cambiado.")
    else:
        form = PasswordChangeBootstrapForm(request.user)
    return render(request, "core/perfil.html", {"form": form})


@gestor_required
def historial(request):
    qs = Auditoria.objects.select_related("usuario", "content_type", "organizacion")
    org = getattr(request, "organizacion", None)
    if org is not None and not request.user.is_superuser:
        qs = qs.filter(Q(organizacion=org) | Q(organizacion__isnull=True))

    accion = request.GET.get("accion", "").strip()
    modelo = request.GET.get("modelo", "").strip()
    usuario = request.GET.get("usuario", "").strip()
    q = request.GET.get("q", "").strip()
    desde = request.GET.get("desde", "").strip()
    hasta = request.GET.get("hasta", "").strip()

    if accion:
        qs = qs.filter(accion=accion)
    if modelo:
        qs = qs.filter(content_type__model=modelo)
    if usuario:
        qs = qs.filter(usuario_nombre__icontains=usuario)
    if q:
        qs = qs.filter(Q(objeto_repr__icontains=q) | Q(cambios__icontains=q))
    if desde:
        qs = qs.filter(fecha__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha__date__lte=hasta)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))
    modelos = (
        Auditoria.objects.exclude(content_type__isnull=True)
        .values_list("content_type__model", flat=True)
        .distinct()
        .order_by("content_type__model")
    )
    return render(
        request,
        "core/historial.html",
        {
            "page_obj": page,
            "acciones": Auditoria._meta.get_field("accion").choices,
            "modelos": modelos,
            "filtros": {
                "accion": accion,
                "modelo": modelo,
                "usuario": usuario,
                "q": q,
                "desde": desde,
                "hasta": hasta,
            },
        },
    )


@login_required
def dashboard_redirect(request):
    return redirect("dashboard")


def manifest(request):
    nombre = "Bosselli Gestión"
    try:
        from .models import Ajuste

        nombre = Ajuste.obtener().nombre_app
    except Exception:
        pass
    data = {
        "name": nombre,
        "short_name": "Bosselli",
        "description": "Gestión interna de las tiendas Bosselli",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f8f5ef",
        "theme_color": "#0f172a",
        "lang": "es",
        "icons": [
            {"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
    }
    return JsonResponse(data, json_dumps_params={"ensure_ascii": False})


def service_worker(request):
    path = os.path.join(settings.BASE_DIR, "static", "sw.js")
    try:
        with open(path, "rb") as f:
            content = f.read()
    except FileNotFoundError:
        content = b"self.addEventListener('fetch', function(){});"
    resp = HttpResponse(content, content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


def health(request):
    return JsonResponse({"ok": True, "app": "bosselli", "hora": timezone.now().isoformat()})


def organizaciones(request):
    """Vista mínima para el superusuario: listado de organizaciones."""
    if not request.user.is_superuser:
        return redirect("dashboard")
    return render(
        request,
        "core/organizaciones.html",
        {"organizaciones": Organizacion.objects.all().order_by("nombre")},
    )
