from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Ajuste, Auditoria, Organizacion, Perfil

admin.site.site_header = "Bosselli Gestión"
admin.site.site_title = "Bosselli"
admin.site.index_title = "Administración"


@admin.register(Organizacion)
class OrganizacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cif", "telefono", "email", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "cif", "email")
    prepopulated_fields = {"slug": ("nombre",)}


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    extra = 1
    fk_name = "user"


class UserAdmin(BaseUserAdmin):
    inlines = [PerfilInline]
    list_display = ("username", "first_name", "last_name", "email", "is_staff", "is_active")
    list_filter = BaseUserAdmin.list_filter + ("perfil__rol",)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("user", "rol", "organizacion", "telefono")
    list_filter = ("rol", "organizacion")
    search_fields = ("user__username", "user__first_name", "user__last_name")
    autocomplete_fields = ("user",)


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario_nombre", "accion", "objeto_repr", "organizacion")
    list_filter = ("accion", "organizacion", "content_type")
    search_fields = ("usuario_nombre", "objeto_repr", "cambios")
    date_hierarchy = "fecha"
    readonly_fields = [f.name for f in Auditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Ajuste)
class AjusteAdmin(admin.ModelAdmin):
    list_display = ("nombre_app", "email_gestoria", "email_avisos")
