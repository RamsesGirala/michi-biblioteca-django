import csv
import datetime

from django.core.exceptions import ValidationError
from django.db.models import Q, Count
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema_view, extend_schema
from rest_framework import viewsets, permissions, mixins
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response

from biblioteca.models import CategoriaLibro, Libro, UsuarioLector, Prestamo
from .permissions import IsSupervisor, IsOperadorOrSupervisor
from .serializers import (
    CategoriaLibroSerializer,
    LibroSerializer,
    UsuarioLectorSerializer,
    PrestamoSerializer,
)
from ..views import es_supervisor, es_operador


class CategoriaLibroViewSet(viewsets.ModelViewSet):

    queryset = CategoriaLibro.objects.all().order_by("nombre")
    serializer_class = CategoriaLibroSerializer

    def get_permissions(self):
        # todas las acciones requieren supervisor
        return [IsSupervisor()]

    def perform_destroy(self, instance: CategoriaLibro):
        # Regla de negocio: no borrar si tiene libros asociados
        if Libro.objects.filter(categoria=instance).exists():
            raise ValidationError(
                "No podés eliminar la categoría porque tiene libros asociados. "
                "Eliminá o reasigná esos libros primero."
            )
        instance.delete()

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH")

    # --------- Listado sin paginación ---------

    @action(detail=False, methods=["get"], pagination_class=None)
    def todos(self, request):
        """
        Devuelve todas las categorías sin paginar.
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class LibroViewSet(viewsets.ModelViewSet):
    serializer_class = LibroSerializer

    def get_queryset(self):
        qs = Libro.objects.select_related("categoria").all().order_by("titulo")

        # búsqueda por título / autor / isbn
        q = self.request.query_params.get("q") or ""
        if q:
            qs = qs.filter(
                Q(titulo__icontains=q)
                | Q(autor__icontains=q)
                | Q(isbn__icontains=q)
            )

        return qs

    def get_permissions(self):
        # list / retrieve -> cualquier usuario autenticado
        if self.action in ["list", "retrieve", "todos"]:
            return [permissions.IsAuthenticated()]
        # crear/actualizar/borrar -> solo supervisores
        return [IsSupervisor()]

    def perform_destroy(self, instance: Libro):
        # Regla: no borrar si hay préstamos asociados
        if Prestamo.objects.filter(libro=instance).exists():
            raise ValidationError(
                "No podés eliminar el libro porque tiene préstamos registrados. "
                "Si no querés seguir prestándolo, dejá ejemplares_totales en 0."
            )
        instance.delete()

    def partial_update(self, request, *args, **kwargs):
        raise MethodNotAllowed("PATCH")

    # --------- Listado sin paginación ---------

    @action(detail=False, methods=["get"], pagination_class=None)
    def todos(self, request):
        """
        Devuelve todos los libros (sin paginación).
        Acepta también ?q= para filtrar por titulo/autor/isbn.
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

class UsuarioLectorViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = UsuarioLector.objects.all().order_by("apellido", "nombre")
    serializer_class = UsuarioLectorSerializer
    pagination_class = None

    def get_permissions(self):
        # Sólo Operador o Supervisor pueden usar este endpoint
        return [IsOperadorOrSupervisor()]

class PrestamoViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):

    serializer_class = PrestamoSerializer

    def get_queryset(self):
        """
        Listado general de préstamos, paginado, con filtro por estado.
        Equivalente a listar_prestamos.
        """
        qs = (
            Prestamo.objects.select_related("libro", "lector")
            .order_by("-fecha_prestamo", "-id")
        )
        estado = self.request.query_params.get("estado") or ""
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            # cualquiera logueado
            return [permissions.IsAuthenticated()]
        if self.action == "create":
            # crear préstamo → operador o supervisor
            return [IsOperadorOrSupervisor()]
        if self.action in ["devolver", "marcar_robado"]:
            # registrar devoluciones y robos → operador o supervisor
            return [IsOperadorOrSupervisor()]
        if self.action == "dashboard":
            # home: cualquier autenticado, comportamiento distinto según rol
            return [permissions.IsAuthenticated()]
        if self.action in ["reporte", "reporte_csv"]:
            # reporte: solo supervisores
            return [IsSupervisor()]
        # fallback
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        """
        Equivalente a crear_prestamo (view):
        - setea creado_por
        - fuerza estado inicial PRESTADO
        La lógica de lector nuevo/existente está en el serializer.
        """
        serializer.save(
            creado_por=self.request.user,
            estado=Prestamo.Estados.PRESTADO,
        )

    # ------- Acciones custom sobre un préstamo -------

    @extend_schema(
        summary="Registrar devolución de un préstamo",
        description=(
            "Marca la devolución de un préstamo. "
            "Si la devolución es posterior a la fecha estimada → ATRASADO, "
            "si no → DEVUELTO."
        ),
        responses=PrestamoSerializer,
    )
    @action(detail=True, methods=["post"])
    def devolver(self, request, pk=None):
        prestamo = self.get_object()
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

        serializer = self.get_serializer(prestamo)
        return Response(serializer.data)

    @extend_schema(
        summary="Marcar préstamo como robado",
        description="Marca el préstamo como ROBADO y setea la fecha_devolucion_real a hoy.",
        responses=PrestamoSerializer,
    )
    @action(detail=True, methods=["post"])
    def marcar_robado(self, request, pk=None):
        prestamo = self.get_object()
        hoy = timezone.localdate()
        prestamo.estado = Prestamo.Estados.ROBADO
        prestamo.fecha_devolucion_real = hoy
        prestamo.save()

        serializer = self.get_serializer(prestamo)
        return Response(serializer.data)

    # ------- Dashboard (home) -------

    @action(detail=False, methods=["get"], url_path="dashboard")
    def dashboard(self, request):
        """
        Equivalente a la vista home:
        - prestamos_activos_recientes: prestados/atrasados de los últimos 7 días
        - si es supervisor:
            - resumen_por_estado global
            - últimos 20 atrasados
        """
        user = request.user
        supervisor = es_supervisor(user)
        operador = es_operador(user)

        hoy = timezone.localdate()
        hace_7_dias = hoy - datetime.timedelta(days=7)

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

        data = {
            "es_supervisor": supervisor,
            "es_operador": operador,
            "hoy": hoy.isoformat(),
            "hace_7_dias": hace_7_dias.isoformat(),
            "prestamos_activos_recientes": self.get_serializer(
                prestamos_activos_recientes, many=True
            ).data,
        }

        if supervisor:
            resumen_raw = (
                Prestamo.objects.values("estado")
                .annotate(total=Count("id"))
                .order_by("estado")
            )
            estado_labels = dict(Prestamo.Estados.choices)
            resumen_por_estado = [
                {
                    "estado": row["estado"],
                    "estado_display": estado_labels.get(row["estado"], row["estado"]),
                    "total": row["total"],
                }
                for row in resumen_raw
            ]

            atrasados = (
                Prestamo.objects.select_related("libro", "lector")
                .filter(estado=Prestamo.Estados.ATRASADO)
                .order_by("-fecha_prestamo")[:20]
            )

            data["resumen_por_estado"] = resumen_por_estado
            data["prestamos_atrasados_recientes"] = self.get_serializer(
                atrasados, many=True
            ).data
        else:
            data["resumen_por_estado"] = None
            data["prestamos_atrasados_recientes"] = None

        return Response(data)

    # ------- Reporte (filtros + resumen + detalle) -------

    def _build_reporte_queryset(self, request):
        qs = Prestamo.objects.select_related(
            "libro", "lector", "libro__categoria"
        ).all()

        estado = (request.query_params.get("estado") or "").strip()
        categoria_id = (request.query_params.get("categoria") or "").strip()
        fecha_desde = (request.query_params.get("fecha_desde") or "").strip()
        fecha_hasta = (request.query_params.get("fecha_hasta") or "").strip()

        if estado:
            qs = qs.filter(estado=estado)
        if categoria_id:
            qs = qs.filter(libro__categoria_id=categoria_id)
        if fecha_desde:
            qs = qs.filter(fecha_prestamo__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha_prestamo__lte=fecha_hasta)

        return qs, estado, categoria_id, fecha_desde, fecha_hasta

    @action(detail=False, methods=["get"], url_path="reporte")
    def reporte(self, request):
        """
        Equivalente a reporte_prestamos (vista HTML), pero en JSON.
        Filtros:
        - estado
        - categoria (id)
        - fecha_desde (YYYY-MM-DD)
        - fecha_hasta (YYYY-MM-DD)
        Devuelve:
        - resumen_por_estado
        - total_prestamos
        - total_atrasados
        - prestamos (detalle completo)
        """
        qs, estado, categoria_id, fecha_desde, fecha_hasta = self._build_reporte_queryset(
            request
        )

        resumen_raw = (
            qs.values("estado")
            .annotate(total=Count("id"))
            .order_by("estado")
        )
        estado_labels = dict(Prestamo.Estados.choices)
        resumen_por_estado = [
            {
                "estado": row["estado"],
                "estado_display": estado_labels.get(row["estado"], row["estado"]),
                "total": row["total"],
            }
            for row in resumen_raw
        ]

        total_prestamos = qs.count()
        total_atrasados = qs.filter(estado=Prestamo.Estados.ATRASADO).count()

        prestamos = qs.order_by("-fecha_prestamo", "-id")

        data = {
            "filtros": {
                "estado": estado,
                "categoria_id": categoria_id,
                "fecha_desde": fecha_desde,
                "fecha_hasta": fecha_hasta,
            },
            "resumen_por_estado": resumen_por_estado,
            "total_prestamos": total_prestamos,
            "total_atrasados": total_atrasados,
            "prestamos": self.get_serializer(prestamos, many=True).data,
        }
        return Response(data)

    # ------- CSV del reporte -------

    @action(detail=False, methods=["get"], url_path="reporte_csv")
    def reporte_csv(self, request):
        """
        Exporta a CSV los préstamos filtrados por los mismos parámetros
        que /api/prestamos/reporte/.
        """
        qs, estado, categoria_id, fecha_desde, fecha_hasta = self._build_reporte_queryset(
            request
        )
        qs = qs.order_by("-fecha_prestamo")

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

        # iterator() para que sea más óptimo en memoria
        for p in qs.iterator():
            writer.writerow(
                [
                    p.id,
                    str(p.libro),
                    str(p.lector),
                    p.get_estado_display(),
                    p.fecha_prestamo,
                    p.fecha_devolucion_estimada,
                    p.fecha_devolucion_real or "",
                    p.libro.categoria.nombre if p.libro and p.libro.categoria else "",
                ]
            )

        return response