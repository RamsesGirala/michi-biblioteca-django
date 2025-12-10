from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from drf_spectacular.views import SpectacularRedocView, SpectacularSwaggerView, SpectacularAPIView

from biblioteca.views import logout_view, permission_denied_403

urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", logout_view, name="logout"),

    path("", include("biblioteca.urls")),
    path("api/", include("biblioteca.api.urls")),

    # 👇 esquema OpenAPI en JSON/YAML
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),

    # 👇 Swagger UI
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),

    # 👇 ReDoc (otra UI alternativa)
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

handler403 = "biblioteca.views.permission_denied_403"