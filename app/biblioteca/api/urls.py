from rest_framework.routers import DefaultRouter
from .views import (
    CategoriaLibroViewSet,
    LibroViewSet,
    UsuarioLectorViewSet,
    PrestamoViewSet,
)

router = DefaultRouter()
router.register(r"categorias", CategoriaLibroViewSet, basename="categoria")
router.register(r"libros", LibroViewSet, basename="libro")
router.register(r"lectores", UsuarioLectorViewSet, basename="lector")
router.register(r"prestamos", PrestamoViewSet, basename="prestamo")

urlpatterns = router.urls
