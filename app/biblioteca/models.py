from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class CategoriaLibro(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoría de libro"
        verbose_name_plural = "Categorías de libros"
        ordering = ["nombre"]

    def __str__(self) -> str:
        return self.nombre

class Libro(models.Model):
    titulo = models.CharField(max_length=200)
    autor = models.CharField(max_length=200)
    # podemos tener libros sin ISBN, pero si está, que sea único
    isbn = models.CharField(max_length=20, blank=True, null=True, unique=True)
    categoria = models.ForeignKey(
        CategoriaLibro,
        on_delete=models.PROTECT,
        related_name="libros",
    )
    fecha_publicacion = models.DateField(blank=True, null=True)

    ejemplares_totales = models.PositiveIntegerField(default=1)
    ejemplares_disponibles = models.PositiveIntegerField(default=1)

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["titulo", "autor"]
        constraints = [
            models.UniqueConstraint(
                fields=["titulo", "autor"],
                name="unique_titulo_autor",
            ),
        ]

    def clean(self):
        super().clean()
        if self.ejemplares_disponibles > self.ejemplares_totales:
            raise ValidationError(
                {"ejemplares_disponibles": "No puede ser mayor que ejemplares_totales."}
            )

    def __str__(self) -> str:
        return f"{self.titulo} ({self.autor})"

    def actualizar_disponibles(self):
        """
        Recalcula ejemplares_disponibles en base a los préstamos activos.
        Activos = PRESTADO o ATRASADO.
        """
        from .models import Prestamo  # import local

        activos = Prestamo.objects.filter(
            libro=self,
            estado__in=Prestamo.ESTADOS_ACTIVOS,
        ).count()

        self.ejemplares_disponibles = max(0, self.ejemplares_totales - activos)
        self.save(update_fields=["ejemplares_disponibles"])

class UsuarioLector(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Lector"
        verbose_name_plural = "Lectores"
        ordering = ["apellido", "nombre"]

    def __str__(self) -> str:
        return f"{self.apellido}, {self.nombre} ({self.dni})"

class Prestamo(models.Model):
    class Estados(models.TextChoices):
        PRESTADO = "PRESTADO", "Prestado"
        DEVUELTO = "DEVUELTO", "Devuelto"
        ATRASADO = "ATRASADO", "Atrasado"
        ROBADO = "ROBADO", "Robado"

    # Estados que cuentan como "ocupan ejemplar"
    ESTADOS_ACTIVOS = (Estados.PRESTADO, Estados.ATRASADO)

    libro = models.ForeignKey(Libro, on_delete=models.PROTECT, related_name="prestamos")
    lector = models.ForeignKey(UsuarioLector, on_delete=models.PROTECT, related_name="prestamos")
    fecha_prestamo = models.DateField()
    fecha_devolucion_estimada = models.DateField()
    fecha_devolucion_real = models.DateField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=Estados.choices,
        default=Estados.PRESTADO,
    )
    comentarios = models.TextField(blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prestamos_creados",
    )

    def clean(self):
        from django.core.exceptions import ValidationError

        errors = {}

        # 1) fechas coherentes
        if (
            self.fecha_devolucion_estimada
            and self.fecha_prestamo
            and self.fecha_devolucion_estimada < self.fecha_prestamo
        ):
            errors.setdefault("fecha_devolucion_estimada", []).append(
                "La fecha estimada de devolución no puede ser anterior a la fecha de préstamo."
            )

        # 2) lector con ATRASADO no puede iniciar nuevo PRESTADO
        #    (sólo cuando es un préstamo nuevo, no al editar uno existente)
        if self.lector_id and self.pk is None and self.estado == Prestamo.Estados.PRESTADO:
            tiene_atrasados = Prestamo.objects.filter(
                lector_id=self.lector_id,
                estado=Prestamo.Estados.ATRASADO,
            ).exists()
            if tiene_atrasados:
                errors.setdefault("__all__", []).append(
                    "El lector tiene préstamos atrasados y no puede solicitar nuevos préstamos."
                )

        # 3) capacidad de ejemplares: no se puede crear PRESTADO si no hay lugar
        if self.libro_id and self.estado == Prestamo.Estados.PRESTADO:
            activos = Prestamo.objects.filter(
                libro_id=self.libro_id,
                estado__in=Prestamo.ESTADOS_ACTIVOS,
            )
            if self.pk:
                activos = activos.exclude(pk=self.pk)

            activos_count = activos.count()
            if (
                self.libro.ejemplares_totales is not None
                and activos_count >= self.libro.ejemplares_totales
            ):
                errors.setdefault("libro", []).append(
                    "No hay ejemplares disponibles para este libro."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # validaciones de negocio
        self.full_clean()
        super().save(*args, **kwargs)
        # actualizar stock del libro
        if self.libro_id:
            self.libro.actualizar_disponibles()

    def esta_atrasado(self):
        """
        Devuelve True si el préstamo está atrasado según el modelo de negocio:
        - estado ATRASADO
        - o estado PRESTADO y la fecha estimada ya pasó.
        """
        if self.estado == Prestamo.Estados.ATRASADO:
            return True

        if (
            self.estado == Prestamo.Estados.PRESTADO
            and self.fecha_devolucion_estimada is not None
        ):
            return timezone.localdate() > self.fecha_devolucion_estimada

        return False

    esta_atrasado.boolean = True
    esta_atrasado.short_description = "¿Atrasado?"