from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
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
]

handler403 = "biblioteca.views.permission_denied_403"