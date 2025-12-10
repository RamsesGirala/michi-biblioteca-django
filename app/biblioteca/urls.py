from django.urls import path
from .views import home, listar_libros, listar_prestamos, crear_prestamo, registrar_devolucion, reporte_prestamos, \
    marcar_prestamo_robado, eliminar_libro, editar_libro, crear_libro, listar_categorias, crear_categoria, \
    editar_categoria, eliminar_categoria

app_name = "biblioteca"

urlpatterns = [
    path("", home, name="home"),

    # Libros
    path("libros/", listar_libros, name="libro_list"),
    path("libros/nuevo/", crear_libro, name="libro_create"),
    path("libros/<int:pk>/editar/", editar_libro, name="libro_edit"),
    path("libros/<int:pk>/eliminar/", eliminar_libro, name="libro_delete"),

    # Categorías
    path("categorias/", listar_categorias, name="categoria_list"),
    path("categorias/nueva/", crear_categoria, name="categoria_create"),
    path("categorias/<int:pk>/editar/", editar_categoria, name="categoria_edit"),
    path("categorias/<int:pk>/eliminar/", eliminar_categoria, name="categoria_delete"),

    # Préstamos
    path("prestamos/", listar_prestamos, name="prestamo_list"),
    path("prestamos/nuevo/", crear_prestamo, name="prestamo_create"),
    path(
        "prestamos/<int:pk>/devolver/",
        registrar_devolucion,
        name="prestamo_devolver",
    ),
    path(
        "prestamos/<int:prestamo_id>/robado/",
        marcar_prestamo_robado,
        name="prestamo_marcar_robado",
    ),

    # Reporte
    path("reportes/prestamos/", reporte_prestamos, name="reporte_prestamos"),
]
