import datetime
from functools import wraps
import logging
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden
from .forms import PrestamoForm, CategoriaLibroForm, LibroForm
from .models import Libro, Prestamo, CategoriaLibro, UsuarioLector

logger = logging.getLogger("biblioteca.audit")

def _get_page_size(request, default=20, max_size=100):
    """
    Lee ?page_size de la querystring, lo convierte a int
    y lo limita entre 1 y max_size.
    """
    raw = request.GET.get("page_size")
    if not raw:
        return default
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(size, max_size))

def es_operador(user) -> bool:
    return user.groups.filter(name="Operador").exists()

def es_supervisor(user) -> bool:
    return user.is_superuser or user.groups.filter(name="Supervisor").exists()

def solo_operadores(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if es_operador(request.user) or es_supervisor(request.user):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("Solo operadores o supervisores pueden hacer esto.")
    return _wrapped

def solo_supervisores(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if es_supervisor(request.user):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("Solo supervisores pueden hacer esto.")
    return _wrapped

@login_required
def home(request):
    user = request.user
    supervisor = es_supervisor(user)
    operador = es_operador(user)

    hoy = timezone.localdate()
    hace_7_dias = hoy - datetime.timedelta(days=7)

    # Préstamos activos (prestados/atrasados) de la última semana
    prestamos_activos_recientes = (
        Prestamo.objects.select_related("libro", "lector")
        .filter(
            estado__in=[
                Prestamo.Estados.PRESTADO,
                Prestamo.Estados.ATRASADO,
            ],
            fecha_prestamo__gte=hace_7_dias,
        )
        .order_by("-fecha_prestamo")
    )

    resumen_por_estado = None
    prestamos_atrasados = None

    if supervisor:
        # resumen global por estado
        resumen_por_estado = (
            Prestamo.objects.values("estado")
            .annotate(total=Count("id"))
            .order_by("estado")
        )

        # últimos atrasados
        prestamos_atrasados = (
            Prestamo.objects.select_related("libro", "lector")
            .filter(estado=Prestamo.Estados.ATRASADO)
            .order_by("-fecha_prestamo")[:20]
        )

    context = {
        "es_supervisor": supervisor,
        "es_operador": operador,
        "prestamos_activos_recientes": prestamos_activos_recientes,
        "resumen_por_estado": resumen_por_estado,
        "prestamos_atrasados": prestamos_atrasados,
        "hace_7_dias": hace_7_dias,
        "hoy": hoy,
    }
    return render(request, "biblioteca/home.html", context)

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

# ========= Categorias =========

@solo_supervisores
def listar_categorias(request):
    user = request.user
    supervisor = es_supervisor(user)
    operador = es_operador(user)

    qs = CategoriaLibro.objects.order_by("nombre")

    page_size = _get_page_size(request, default=20)
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "es_supervisor": supervisor,
        "es_operador": operador,
        "page_size": page_size,
    }
    return render(request, "biblioteca/categoria_list.html", context)

@login_required
@solo_supervisores
def crear_categoria(request):
    if request.method == "POST":
        form = CategoriaLibroForm(request.POST)
        if form.is_valid():
            categoria = form.save()
            logger.info(
                "CATEGORIA_CREATE user=%s categoria_id=%s nombre=%s",
                request.user.username,
                categoria.id,
                categoria.nombre,
            )
            messages.success(request, "Categoría creada correctamente.")
            return redirect("biblioteca:categoria_list")
    else:
        form = CategoriaLibroForm()

    return render(request, "biblioteca/categoria_form.html", {"form": form})

@login_required
@solo_supervisores
def editar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaLibro, pk=pk)
    if request.method == "POST":
        form = CategoriaLibroForm(request.POST, instance=categoria)
        if form.is_valid():
            categoria = form.save()
            logger.info(
                "CATEGORIA_UPDATE user=%s categoria_id=%s nombre=%s",
                request.user.username,
                categoria.id,
                categoria.nombre,
            )
            messages.success(request, "Categoría actualizada correctamente.")
            return redirect("biblioteca:categoria_list")
    else:
        form = CategoriaLibroForm(instance=categoria)

    return render(
        request,
        "biblioteca/categoria_form.html",
        {"form": form, "categoria": categoria},
    )

@login_required
@solo_supervisores
def eliminar_categoria(request, pk):
    categoria = get_object_or_404(CategoriaLibro, pk=pk)

    if request.method == "POST":
        # NO permitimos borrar si tiene libros
        tiene_libros = Libro.objects.filter(categoria=categoria).exists()
        if tiene_libros:
            messages.error(
                request,
                "No podés eliminar la categoría porque tiene libros asociados. "
                "Eliminá o reasigná esos libros primero.",
            )
            return redirect("biblioteca:categoria_list")
        cat_id = categoria.id
        cat_nombre = categoria.nombre
        categoria.delete()
        logger.info(
            "CATEGORIA_DELETE user=%s categoria_id=%s nombre=%s",
            request.user.username,
            cat_id,
            cat_nombre,
        )
        messages.success(request, "Categoría eliminada correctamente.")
        return redirect("biblioteca:categoria_list")

    return render(
        request,
        "biblioteca/categoria_confirm_delete.html",
        {"categoria": categoria},
    )

# ========= Libros  =========
@login_required
def listar_libros(request):
    user = request.user
    supervisor = es_supervisor(user)
    operador = es_operador(user)

    qs = Libro.objects.select_related("categoria").order_by("titulo")

    page_size = _get_page_size(request, default=20)
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "es_supervisor": supervisor,
        "es_operador": operador,
        "page_size": page_size,
    }
    return render(request, "biblioteca/libro_list.html", context)

@login_required
@solo_supervisores
def crear_libro(request):
    if request.method == "POST":
        form = LibroForm(request.POST)
        if form.is_valid():
            libro = form.save()
            logger.info(
                "LIBRO_CREATE user=%s libro_id=%s titulo=%s",
                request.user.username,
                libro.id,
                libro.titulo,
            )
            messages.success(request, "Libro creado correctamente.")
            return redirect("biblioteca:libro_list")
    else:
        form = LibroForm()

    return render(request, "biblioteca/libro_form.html", {"form": form})

@login_required
@solo_supervisores
def editar_libro(request, pk):
    libro = get_object_or_404(Libro, pk=pk)
    if request.method == "POST":
        form = LibroForm(request.POST, instance=libro)
        if form.is_valid():
            libro = form.save()
            logger.info(
                "LIBRO_UPDATE user=%s libro_id=%s titulo=%s",
                request.user.username,
                libro.id,
                libro.titulo,
            )
            messages.success(request, "Libro actualizado correctamente.")
            return redirect("biblioteca:libro_list")
    else:
        form = LibroForm(instance=libro)

    return render(
        request, "biblioteca/libro_form.html", {"form": form, "libro": libro}
    )

@login_required
@solo_supervisores
def eliminar_libro(request, pk):
    libro = get_object_or_404(Libro, pk=pk)

    if request.method == "POST":
        # NO permitimos borrar libros con préstamos
        tiene_prestamos = Prestamo.objects.filter(libro=libro).exists()
        if tiene_prestamos:
            messages.error(
                request,
                "No podés eliminar el libro porque tiene préstamos registrados. "
                "Si no querés seguir prestándolo, dejá ejemplares_totales en 0.",
            )
            return redirect("biblioteca:libro_list")

        libro_id = libro.id
        titulo = libro.titulo
        libro.delete()

        logger.info(
            "LIBRO_DELETE user=%s libro_id=%s titulo=%s",
            request.user.username,
            libro_id,
            titulo,
        )
        messages.success(request, "Libro eliminado correctamente.")
        return redirect("biblioteca:libro_list")

    return render(
        request,
        "biblioteca/libro_confirm_delete.html",
        {"libro": libro},
    )

# ========= Préstamos =========

@login_required
def listar_prestamos(request):
    """
    Lista de préstamos paginada, con filtro por estado.
    Muestra acciones según el rol (operador/supervisor).
    """
    user = request.user
    supervisor = es_supervisor(user)
    operador = es_operador(user)

    estado = request.GET.get("estado") or ""

    qs = Prestamo.objects.select_related("libro", "lector").order_by(
        "-fecha_prestamo", "-id"
    )

    if estado:
        qs = qs.filter(estado=estado)

    page_size = _get_page_size(request, default=20)
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get("page") or 1
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "prestamo_estados": Prestamo.Estados.choices,
        "estado": estado,
        "es_supervisor": supervisor,
        "es_operador": operador,
        "page_size": page_size,
    }
    return render(request, "biblioteca/prestamo_list.html", context)

@login_required
@solo_operadores
def crear_prestamo(request):
    """
    Crear un préstamo nuevo.
    Operador (o supervisor/admin) pueden crear.
    Permite elegir lector existente o crear uno nuevo.
    """
    if request.method == "POST":
        form = PrestamoForm(request.POST)
        if form.is_valid():
            crear_nuevo = form.cleaned_data["crear_nuevo_lector"]

            if crear_nuevo:
                # Crear lector nuevo
                lector = UsuarioLector.objects.create(
                    nombre=form.cleaned_data["nombre_lector"],
                    apellido=form.cleaned_data["apellido_lector"],
                    dni=form.cleaned_data["dni_lector"],
                    activo=True,
                )
            else:
                lector = form.cleaned_data["lector"]

            prestamo = form.save(commit=False)
            prestamo.lector = lector
            prestamo.creado_por = request.user
            prestamo.estado = Prestamo.Estados.PRESTADO
            prestamo.save()  # esto dispara clean() y actualizar_disponibles()

            logger.info(
                "PRESTAMO_CREATE user=%s prestamo_id=%s libro_id=%s lector_id=%s",
                request.user.username,
                prestamo.id,
                prestamo.libro_id,
                prestamo.lector_id,
            )

            messages.success(request, "Préstamo creado correctamente.")
            return redirect("biblioteca:prestamo_list")
    else:
        initial = {"fecha_prestamo": timezone.localdate()}
        form = PrestamoForm(initial=initial)

    return render(request, "biblioteca/prestamo_form.html", {"form": form})

@login_required
def registrar_devolucion(request, pk):
    """
    Permite registrar la devolución de un préstamo.
    - Si se devuelve después de la fecha estimada => ATRASADO
    - Si se devuelve en fecha o antes => DEVUELTO
    """
    prestamo = get_object_or_404(Prestamo, pk=pk)

    if request.method == "POST":
        hoy = timezone.localdate()
        prestamo.fecha_devolucion_real = hoy

        if (
            prestamo.fecha_devolucion_estimada
            and hoy > prestamo.fecha_devolucion_estimada
        ):
            prestamo.estado = Prestamo.Estados.ATRASADO
        else:
            prestamo.estado = Prestamo.Estados.DEVUELTO

        prestamo.save()

        logger.info(
            "PRESTAMO_DEVOLUCION user=%s prestamo_id=%s nuevo_estado=%s",
            request.user.username,
            prestamo.id,
            prestamo.estado,
        )

        messages.success(request, "Devolución registrada correctamente.")
        return redirect("biblioteca:prestamo_list")

    return render(
        request,
        "biblioteca/prestamo_confirm_devolver.html",
        {"prestamo": prestamo},
    )

@login_required
def marcar_prestamo_robado(request, pk):
    if not (es_operador(request.user) or es_supervisor(request.user)):
        return HttpResponseForbidden()

    prestamo = get_object_or_404(Prestamo, pk=pk)

    if request.method == "POST":
        prestamo.estado = Prestamo.Estados.ROBADO
        prestamo.fecha_devolucion_real = timezone.localdate()
        prestamo.save()
        logger.info(
            "PRESTAMO_ROBADO user=%s prestamo_id=%s",
            request.user.username,
            prestamo.id,
        )
        messages.warning(request, "Préstamo marcado como ROBADO.")
        return redirect("biblioteca:prestamo_list")

    return render(request, "biblioteca/prestamo_confirm_robado.html", {"prestamo": prestamo})

@login_required
@solo_supervisores
def reporte_prestamos(request):
    """
    Reporte de préstamos con filtros y exportación a CSV.
    Solo supervisores/admin.
    """
    qs = Prestamo.objects.select_related("libro", "lector", "libro__categoria")

    estado = (request.GET.get("estado") or "").strip()
    categoria_id = (request.GET.get("categoria") or "").strip()
    fecha_desde = (request.GET.get("fecha_desde") or "").strip()
    fecha_hasta = (request.GET.get("fecha_hasta") or "").strip()

    if estado:
        qs = qs.filter(estado=estado)
    if categoria_id:
        qs = qs.filter(libro__categoria_id=categoria_id)
    if fecha_desde:
        qs = qs.filter(fecha_prestamo__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_prestamo__lte=fecha_hasta)

    # métricas
    resumen_por_estado = (
        qs.values("estado")
        .annotate(total=Count("id"))
        .order_by("estado")
    )
    total_prestamos = qs.count()
    total_atrasados = qs.filter(estado=Prestamo.Estados.ATRASADO).count()

    # CSV
    if request.GET.get("export") == "csv":
        import csv

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="reporte_prestamos.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "ID",
                "Libro",
                "Lector",
                "Estado",
                "Fecha préstamo",
                "Fecha estimada devolución",
                "Fecha devolución real",
                "Categoría",
            ]
        )
        for p in qs.order_by("-fecha_prestamo"):
            writer.writerow(
                [
                    p.id,
                    str(p.libro),
                    str(p.lector),
                    p.get_estado_display(),
                    p.fecha_prestamo,
                    p.fecha_devolucion_estimada,
                    p.fecha_devolucion_real or "",
                    p.libro.categoria.nombre,
                ]
            )
        return response

    categorias = CategoriaLibro.objects.all().order_by("nombre")

    context = {
        "prestamos": qs.order_by("-fecha_prestamo")[:100],  # top 100 para la vista
        "resumen_por_estado": resumen_por_estado,
        "total_prestamos": total_prestamos,
        "total_atrasados": total_atrasados,
        "estado": estado,
        "categoria_id": categoria_id,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "categorias": categorias,
        "prestamo_estados": Prestamo.Estados.choices,
    }
    return render(request, "biblioteca/reporte_prestamos.html", context)

def permission_denied_403(request, exception=None):
    """
    Vista para errores 403 (Permiso denegado).
    La usamos como handler global.
    """
    return render(request, "403.html", status=403)