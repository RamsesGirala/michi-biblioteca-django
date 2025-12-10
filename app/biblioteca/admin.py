from django.contrib import admin
from .models import CategoriaLibro, Libro, UsuarioLector, Prestamo


@admin.register(CategoriaLibro)
class CategoriaLibroAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)
    list_filter = ("activo",)


@admin.register(Libro)
class LibroAdmin(admin.ModelAdmin):
    list_display = (
        "titulo",
        "autor",
        "categoria",
        "isbn",
        "ejemplares_totales",
        "ejemplares_disponibles",
        "activo",
    )
    search_fields = ("titulo", "autor", "isbn")
    list_filter = ("categoria", "activo")
    list_editable = ("ejemplares_totales", "ejemplares_disponibles", "activo")
    autocomplete_fields = ("categoria",)


@admin.register(UsuarioLector)
class UsuarioLectorAdmin(admin.ModelAdmin):
    list_display = ("apellido", "nombre", "dni", "email", "activo")
    search_fields = ("apellido", "nombre", "dni", "email")
    list_filter = ("activo",)


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "libro",
        "lector",
        "estado",
        "fecha_prestamo",
        "fecha_devolucion_estimada",
        "fecha_devolucion_real",
        "creado_por",
    )
    list_filter = ("estado", "libro", "lector", "creado_por")
    search_fields = (
        "libro__titulo",
        "libro__autor",
        "lector__apellido",
        "lector__nombre",
        "lector__dni",
    )
    date_hierarchy = "fecha_prestamo"
    autocomplete_fields = ("libro", "lector", "creado_por")
    readonly_fields = ("esta_atrasado",)

    fieldsets = (
        (
            "Datos del préstamo",
            {
                "fields": (
                    "libro",
                    "lector",
                    "estado",
                    "fecha_prestamo",
                    "fecha_devolucion_estimada",
                    "fecha_devolucion_real",
                    "esta_atrasado",
                )
            },
        ),
        (
            "Metadatos",
            {
                "fields": (
                    "creado_por",
                    "comentarios",
                )
            },
        ),
    )
