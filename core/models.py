from contextvars import ContextVar

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


# ---------------------------------------------------------------------------
# Contexto de organización (multi-tenant) y de auditoría
# ---------------------------------------------------------------------------
_org_context: ContextVar = ContextVar("org_context", default=None)
_audit_context: ContextVar = ContextVar("audit_context", default=None)

TENANT_MODELS = set()


def get_current_org():
    return _org_context.get()


def set_current_org(org):
    return _org_context.set(org)


def get_audit_context():
    return _audit_context.get()


def set_audit_context(ctx):
    return _audit_context.set(ctx)


class Organizacion(models.Model):
    nombre = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    cif = models.CharField("CIF", max_length=20, blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    web = models.URLField(blank=True)
    logo = models.ImageField(upload_to="organizaciones/", blank=True, null=True)
    color = models.CharField(max_length=20, default="#0f172a")
    activa = models.BooleanField(default=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Organización"
        verbose_name_plural = "Organizaciones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class TenantManager(models.Manager):
    """Filtra automáticamente por la organización activa en el contexto."""

    def get_queryset(self):
        qs = super().get_queryset()
        org = _org_context.get()
        if org is not None:
            return qs.filter(organizacion=org)
        return qs


class TenantModel(models.Model):
    organizacion = models.ForeignKey(
        Organizacion, on_delete=models.CASCADE, related_name="%(class)s_set"
    )
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not getattr(cls._meta, "abstract", True):
            TENANT_MODELS.add(cls)


ROL_CHOICES = [
    ("admin", "Administrador"),
    ("gestor", "Gestor/a"),
    ("vendedor", "Vendedor/a"),
    ("contable", "Contable"),
]


class Perfil(TenantModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default="vendedor")
    telefono = models.CharField(max_length=30, blank=True)

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.get_rol_display()})"

    @property
    def es_admin(self):
        return self.rol == "admin" or self.user.is_superuser

    @property
    def es_gestor(self):
        return self.rol in ("admin", "gestor") or self.user.is_superuser


ACCION_CHOICES = [
    ("crear", "Crear"),
    ("editar", "Editar"),
    ("borrar", "Borrar"),
    ("login", "Login"),
    ("logout", "Logout"),
    ("login_fallido", "Login fallido"),
    ("exportar", "Exportar"),
    ("importar", "Importar"),
    ("cambio_estado", "Cambio de estado"),
    ("envio_email", "Envío de email"),
    ("envio_aviso", "Envío de aviso"),
    ("otro", "Otro"),
]


class Auditoria(TenantModel):
    organizacion = models.ForeignKey(
        Organizacion, on_delete=models.SET_NULL, null=True, blank=True, related_name="auditorias"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="auditorias"
    )
    usuario_nombre = models.CharField(max_length=150, blank=True)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES, default="otro")
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    objeto_repr = models.CharField(max_length=255, blank=True)
    cambios = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    ruta = models.CharField(max_length=500, blank=True)
    metodo = models.CharField(max_length=10, blank=True)

    objects = models.Manager()

    class Meta:
        verbose_name = "Auditoría"
        verbose_name_plural = "Auditorías"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.usuario_nombre} {self.accion} {self.objeto_repr}"


TENANT_MODELS.discard(Auditoria)


class Ajuste(models.Model):
    """Ajustes globales de la aplicación (uno solo)."""

    nombre_app = models.CharField(max_length=120, default="Bosselli Gestión")
    lema = models.CharField(max_length=200, default="Sastrería y moda clásica desde 1973")
    email_gestoria = models.EmailField(blank=True)
    email_avisos = models.EmailField(blank=True)
    pie_ticket = models.CharField(
        max_length=255,
        blank=True,
        default="Gracias por confiar en Bosselli. Sastrería y moda clásica desde 1973.",
    )

    class Meta:
        verbose_name = "Ajuste"
        verbose_name_plural = "Ajustes"

    def __str__(self):
        return self.nombre_app

    @classmethod
    def obtener(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
