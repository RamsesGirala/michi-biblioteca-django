import random
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from biblioteca.models import (
    CategoriaLibro,
    Libro,
    UsuarioLector,
    Prestamo,
)


class Command(BaseCommand):
    help = "Inicializa la base con datos de ejemplo para la biblioteca."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Borrando datos previos de biblioteca..."))

        Prestamo.objects.all().delete()
        Libro.objects.all().delete()
        UsuarioLector.objects.all().delete()
        CategoriaLibro.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Datos previos borrados."))

        # Usuario creador para los préstamos de demo
        User = get_user_model()
        usuario_creador, _ = User.objects.get_or_create(
            username="seed_user",
            defaults={
                "email": "seed_user@example.com",
                "is_staff": True,
                "is_superuser": False,
            },
        )

        # 1) Categorías + libros reales
        categorias_data = {
            "Novela": [
                ("1984", "George Orwell"),
                ("Rebelión en la granja", "George Orwell"),
                ("El nombre de la rosa", "Umberto Eco"),
                ("Crimen y castigo", "Fiódor Dostoievski"),
                ("El extranjero", "Albert Camus"),
                ("Los hermanos Karamazov", "Fiódor Dostoievski"),
                ("Rayuela", "Julio Cortázar"),
            ],
            "Tecnología": [
                ("Clean Code", "Robert C. Martin"),
                ("Clean Architecture", "Robert C. Martin"),
                ("Design Patterns", "Gamma, Helm, Johnson, Vlissides"),
                ("Introduction to Algorithms", "Cormen, Leiserson, Rivest, Stein"),
                ("The Pragmatic Programmer", "Andrew Hunt, David Thomas"),
                ("Refactoring", "Martin Fowler"),
            ],
            "Historia": [
                ("Sapiens", "Yuval Noah Harari"),
                ("Homo Deus", "Yuval Noah Harari"),
                ("El diario de Ana Frank", "Ana Frank"),
                ("El arte de la guerra", "Sun Tzu"),
                ("Los mitos de la historia argentina", "Felipe Pigna"),
                ("La Segunda Guerra Mundial", "Antony Beevor"),
            ],
            "Fantasía": [
                ("Harry Potter y la piedra filosofal", "J. K. Rowling"),
                ("Harry Potter y la cámara secreta", "J. K. Rowling"),
                ("El señor de los anillos", "J. R. R. Tolkien"),
                ("El hobbit", "J. R. R. Tolkien"),
                ("Canción de hielo y fuego", "George R. R. Martin"),
                ("El nombre del viento", "Patrick Rothfuss"),
            ],
            "Infantil": [
                ("El principito", "Antoine de Saint-Exupéry"),
                ("Alicia en el país de las maravillas", "Lewis Carroll"),
                ("Matilda", "Roald Dahl"),
                ("Charlie y la fábrica de chocolate", "Roald Dahl"),
                ("Pinocho", "Carlo Collodi"),
                ("Caperucita Roja", "Hermanos Grimm"),
            ],
        }

        self.stdout.write(self.style.WARNING("Creando categorías y libros reales..."))

        categorias = {}
        libros = []

        # Crear categorías
        for nombre_cat in categorias_data.keys():
            cat = CategoriaLibro.objects.create(nombre=nombre_cat, activo=True)
            categorias[nombre_cat] = cat

        self.stdout.write(self.style.SUCCESS(f"Categorías creadas: {len(categorias)}"))

        # Crear libros dentro de cada categoría
        for nombre_cat, lista_libros in categorias_data.items():
            cat = categorias[nombre_cat]
            for titulo, autor in lista_libros:
                libro = Libro.objects.create(
                    titulo=titulo,
                    autor=autor,
                    categoria=cat,
                    ejemplares_totales=3,
                    ejemplares_disponibles=3,
                )
                libros.append(libro)

        self.stdout.write(self.style.SUCCESS(f"Libros creados: {len(libros)}"))

        # 2) Lectores
        nombres = [
            "Juan",
            "Ana",
            "Carlos",
            "María",
            "Lucía",
            "Pedro",
            "Sofía",
            "Diego",
            "Laura",
            "Martín",
        ]
        apellidos = [
            "Pérez",
            "García",
            "López",
            "Rodríguez",
            "Fernández",
            "Gómez",
            "Sánchez",
            "Díaz",
            "Martínez",
            "Romero",
        ]

        lectores = []
        dni_base = 20000000
        for i in range(10):
            lector = UsuarioLector.objects.create(
                nombre=nombres[i],
                apellido=apellidos[i],
                dni=str(dni_base + i),
                activo=True,
            )
            lectores.append(lector)

        self.stdout.write(self.style.SUCCESS(f"Creaste {len(lectores)} lectores."))

        hoy = timezone.localdate()
        prestamos_creados = []
        lectores_con_atraso = set()  # ids de lectores "bloqueados" para nuevos PRESTADO
        MAX_ATRASADOS = 3  # como máximo 3 lectores con préstamos ATRASADO

        # Helper para crear préstamo con lógica de fechas coherente
        def crear_prestamo(libro, lector, estado):
            dias_atras = random.randint(5, 90)
            fecha_prestamo = hoy - datetime.timedelta(days=dias_atras)
            fecha_estimada = fecha_prestamo + datetime.timedelta(days=14)
            fecha_real = None

            if estado == Prestamo.Estados.DEVUELTO:
                diff = random.randint(0, 5)
                fecha_real = fecha_estimada + datetime.timedelta(days=diff)
                if fecha_real < fecha_prestamo:
                    fecha_real = fecha_prestamo

            elif estado == Prestamo.Estados.ATRASADO:
                # estimada en el pasado y >= fecha_prestamo
                if fecha_estimada >= hoy:
                    fecha_prestamo_local = hoy - datetime.timedelta(days=30)
                    fecha_estimada_local = hoy - datetime.timedelta(days=7)
                else:
                    fecha_prestamo_local = fecha_prestamo
                    fecha_estimada_local = fecha_estimada
                fecha_prestamo = fecha_prestamo_local
                fecha_estimada = fecha_estimada_local
                # sin fecha_real -> sigue atrasado

            elif estado == Prestamo.Estados.PRESTADO:
                # aseguramos que la estimada esté en el futuro
                if fecha_estimada <= hoy:
                    fecha_estimada = hoy + datetime.timedelta(days=random.randint(3, 15))

            # ROBADO: usamos las fechas tal como quedaron; sólo importa que estimada >= prestamo
            prestamo = Prestamo(
                libro=libro,
                lector=lector,
                fecha_prestamo=fecha_prestamo,
                fecha_devolucion_estimada=fecha_estimada,
                fecha_devolucion_real=fecha_real,
                estado=estado,
                comentarios="Préstamo generado para datos de prueba.",
                creado_por=usuario_creador,
            )
            prestamo.save()
            return prestamo

        # 3) Casos especiales buscados

        # 3.1 Libro con varios préstamos activos (2 activos, 1 libre)
        libro_multi = libros[0]
        libro_multi.ejemplares_totales = 3
        libro_multi.ejemplares_disponibles = 3
        libro_multi.save()

        lector1 = lectores[0]
        lector2 = lectores[1]

        p1 = crear_prestamo(
            libro_multi, lector1, Prestamo.Estados.PRESTADO
        )  # activo
        p2 = crear_prestamo(
            libro_multi, lector2, Prestamo.Estados.PRESTADO
        )  # activo
        prestamos_creados.extend([p1, p2])

        # 3.2 Libro con todos los ejemplares actualmente prestados (capacidad llena)
        libro_full = libros[1]
        libro_full.ejemplares_totales = 3
        libro_full.ejemplares_disponibles = 3
        libro_full.save()

        lector3 = lectores[2]
        lector4 = lectores[3]
        lector5 = lectores[4]

        p3 = crear_prestamo(libro_full, lector3, Prestamo.Estados.PRESTADO)
        p4 = crear_prestamo(libro_full, lector4, Prestamo.Estados.PRESTADO)
        p5 = crear_prestamo(libro_full, lector5, Prestamo.Estados.PRESTADO)
        prestamos_creados.extend([p3, p4, p5])

        # 3.3 Lector con préstamo ATRASADO (no debe poder recibir nuevos PRESTADO)
        libro_atrasado = libros[2]
        lector_atrasado = lectores[5]
        p6 = crear_prestamo(libro_atrasado, lector_atrasado, Prestamo.Estados.ATRASADO)
        prestamos_creados.append(p6)
        lectores_con_atraso.add(lector_atrasado.id)

        # 4) Resto de libros con mezcla de estados
        estados_posibles = [
            Prestamo.Estados.PRESTADO,
            Prestamo.Estados.DEVUELTO,
            Prestamo.Estados.ATRASADO,
            Prestamo.Estados.ROBADO,
        ]

        for libro in libros[3:]:
            # entre 0 y 3 préstamos por libro
            num_prestamos = random.randint(0, 3)

            for _ in range(num_prestamos):
                estado = random.choice(estados_posibles)

                # Limitar cantidad de lectores con ATRASADO
                if (
                    estado == Prestamo.Estados.ATRASADO
                    and len(lectores_con_atraso) >= MAX_ATRASADOS
                ):
                    # ya hay suficientes lectores con atraso -> degradamos a DEVUELTO
                    estado = Prestamo.Estados.DEVUELTO

                # Chequeamos capacidad del libro si el estado sería activo
                if estado in (Prestamo.Estados.ATRASADO, Prestamo.Estados.PRESTADO):
                    activos_count = Prestamo.objects.filter(
                        libro=libro,
                        estado__in=[
                            Prestamo.Estados.ATRASADO,
                            Prestamo.Estados.PRESTADO,
                        ],
                    ).count()
                    if activos_count >= libro.ejemplares_totales:
                        # Sin capacidad: degradamos a DEVUELTO para no violar la regla
                        estado = Prestamo.Estados.DEVUELTO

                # Elegimos lector respetando regla de atrasados
                if estado == Prestamo.Estados.ATRASADO:
                    # elegimos un lector sin atraso aún para generarle uno
                    lectores_sin_atraso = [
                        l for l in lectores if l.id not in lectores_con_atraso
                    ]
                    if lectores_sin_atraso:
                        lector = random.choice(lectores_sin_atraso)
                    else:
                        lector = random.choice(lectores)
                    lectores_con_atraso.add(lector.id)
                elif estado == Prestamo.Estados.PRESTADO:
                    # sólo lectores sin atrasos
                    lectores_sin_atraso = [
                        l for l in lectores if l.id not in lectores_con_atraso
                    ]
                    if not lectores_sin_atraso:
                        # Si no queda ninguno, caemos a DEVUELTO
                        estado = Prestamo.Estados.DEVUELTO
                        lector = random.choice(lectores)
                    else:
                        lector = random.choice(lectores_sin_atraso)
                else:
                    # DEVUELTO / ROBADO
                    lector = random.choice(lectores)

                prestamo = crear_prestamo(libro, lector, estado)
                prestamos_creados.append(prestamo)

        self.stdout.write(
            self.style.SUCCESS(
                f"Creaste {len(prestamos_creados)} préstamos de ejemplo."
            )
        )
        self.stdout.write(self.style.SUCCESS("Datos de demo cargados OK."))
