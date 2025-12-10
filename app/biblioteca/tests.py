import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CategoriaLibro, Libro, UsuarioLector, Prestamo


User = get_user_model()


class BaseTestDataMixin:
    @classmethod
    def setUpTestData(cls):
        # Grupos
        cls.grupo_operador = Group.objects.create(name="Operador")
        cls.grupo_supervisor = Group.objects.create(name="Supervisor")

        # Usuarios
        cls.operador = User.objects.create_user(
            username="operador",
            password="operador123",
        )
        cls.operador.groups.add(cls.grupo_operador)

        cls.supervisor = User.objects.create_user(
            username="supervisor",
            password="supervisor123",
        )
        cls.supervisor.groups.add(cls.grupo_supervisor)

        cls.admin = User.objects.create_superuser(
            username="admin",
            password="admin123",
            email="admin@example.com",
        )

        # Datos de biblioteca
        cls.categoria = CategoriaLibro.objects.create(nombre="Novela")
        cls.libro = Libro.objects.create(
            titulo="1984",
            autor="George Orwell",
            categoria=cls.categoria,
            ejemplares_totales=2,
            ejemplares_disponibles=2,
        )
        cls.lector = UsuarioLector.objects.create(
            nombre="Juan",
            apellido="Pérez",
            dni="12345678",
        )

        cls.fecha_prestamo = datetime.date(2025, 1, 1)
        cls.fecha_estimada = datetime.date(2025, 1, 10)

        # Un préstamo activo inicial (PRESTADO)
        cls.prestamo = Prestamo.objects.create(
            libro=cls.libro,
            lector=cls.lector,
            fecha_prestamo=cls.fecha_prestamo,
            fecha_devolucion_estimada=cls.fecha_estimada,
            estado=Prestamo.Estados.PRESTADO,
            creado_por=cls.supervisor,
        )


class PrestamoModelTests(BaseTestDataMixin, TestCase):
    def test_fecha_devolucion_estimada_no_puede_ser_anterior_a_prestamo(self):
        """El modelo Prestamo debe validar que fecha_estimada >= fecha_prestamo."""
        prestamo = Prestamo(
            libro=self.libro,
            lector=self.lector,
            fecha_prestamo=datetime.date(2025, 1, 10),
            fecha_devolucion_estimada=datetime.date(2025, 1, 5),  # anterior
            estado=Prestamo.Estados.PRESTADO,
            creado_por=self.supervisor,
        )
        with self.assertRaises(ValidationError):
            prestamo.full_clean()

    def test_no_se_permite_prestamo_activo_si_no_hay_ejemplares_disponibles(self):
        """
        No debería permitirse un préstamo activo (PRESTADO)
        si el libro ya no tiene capacidad (activos >= ejemplares_totales).
        """
        # Ya tenemos 1 PRESTADO en setUpTestData, y el libro tiene ejemplares_totales=2.
        # Creamos un segundo préstamo activo válido.
        prestamo2 = Prestamo(
            libro=self.libro,
            lector=self.lector,
            fecha_prestamo=datetime.date(2025, 1, 2),
            fecha_devolucion_estimada=datetime.date(2025, 1, 15),
            estado=Prestamo.Estados.PRESTADO,
            creado_por=self.supervisor,
        )
        prestamo2.full_clean()
        prestamo2.save()

        # Ahora activos = 2 (capacidad llena). Un tercero debe fallar.
        prestamo3 = Prestamo(
            libro=self.libro,
            lector=self.lector,
            fecha_prestamo=datetime.date(2025, 1, 3),
            fecha_devolucion_estimada=datetime.date(2025, 1, 20),
            estado=Prestamo.Estados.PRESTADO,
            creado_por=self.supervisor,
        )
        with self.assertRaises(ValidationError):
            prestamo3.full_clean()

    def test_no_se_permite_prestamo_a_lector_con_prestamo_atrasado(self):
        """
        Si un lector tiene al menos un préstamo ATRASADO, no puede recibir nuevos
        préstamos activos (PRESTADO).
        """
        # Marcamos el préstamo inicial como ATRASADO
        self.prestamo.estado = Prestamo.Estados.ATRASADO
        self.prestamo.save()

        # Intentamos crear un nuevo préstamo activo para el mismo lector
        nuevo = Prestamo(
            libro=self.libro,
            lector=self.lector,
            fecha_prestamo=datetime.date(2025, 2, 1),
            fecha_devolucion_estimada=datetime.date(2025, 2, 10),
            estado=Prestamo.Estados.PRESTADO,
            creado_por=self.supervisor,
        )
        with self.assertRaises(ValidationError):
            nuevo.full_clean()


class PermisosReporteTests(BaseTestDataMixin, TestCase):
    def test_operador_no_puede_acceder_a_reporte(self):
        self.client.login(username="operador", password="operador123")
        url = reverse("biblioteca:reporte_prestamos")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_supervisor_puede_acceder_a_reporte(self):
        self.client.login(username="supervisor", password="supervisor123")
        url = reverse("biblioteca:reporte_prestamos")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reporte de préstamos")


class PrestamoViewsTests(BaseTestDataMixin, TestCase):
    def test_operador_puede_crear_prestamo(self):
        """
        El operador puede crear un préstamo cuando hay ejemplares disponibles
        y el lector no tiene préstamos atrasados.
        """
        self.client.login(username="operador", password="operador123")
        url = reverse("biblioteca:prestamo_create")

        # Liberamos el préstamo inicial (lo marcamos como DEVUELTO)
        self.prestamo.estado = Prestamo.Estados.DEVUELTO
        self.prestamo.fecha_devolucion_real = self.prestamo.fecha_devolucion_estimada
        self.prestamo.save()

        fecha_prestamo = timezone.localdate()
        fecha_estimada = fecha_prestamo + datetime.timedelta(days=7)

        data = {
            "libro": self.libro.id,
            "lector": self.lector.id,
            "fecha_prestamo": fecha_prestamo,
            "fecha_devolucion_estimada": fecha_estimada,
            "comentarios": "Préstamo de prueba",
            # no marcamos crear_nuevo_lector => usa lector existente
        }

        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Uno devuelto + uno nuevo activo
        self.assertEqual(Prestamo.objects.count(), 2)
        nuevo = Prestamo.objects.latest("id")
        self.assertEqual(nuevo.libro, self.libro)
        self.assertEqual(nuevo.lector, self.lector)
        self.assertEqual(nuevo.creado_por, self.operador)
        self.assertEqual(nuevo.estado, Prestamo.Estados.PRESTADO)

    def test_supervisor_puede_registrar_devolucion(self):
        self.client.login(username="supervisor", password="supervisor123")
        url = reverse("biblioteca:prestamo_devolver", args=[self.prestamo.id])

        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)

        self.prestamo.refresh_from_db()
        self.assertIn(
            self.prestamo.estado,
            [Prestamo.Estados.DEVUELTO, Prestamo.Estados.ATRASADO],
        )
        self.assertIsNotNone(self.prestamo.fecha_devolucion_real)
