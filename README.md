# Sistema de Biblioteca Michi

Pequeño sistema de gestión de biblioteca hecho con **Django** y **Docker**, pensado para practicar:

- Roles de usuario (Operador / Supervisor / Admin).
- Gestión de préstamos con estados (PRESTADO, DEVUELTO, ATRASADO, ROBADO).
- Paginación configurable vía querystring.
- Auditoría simple vía logs.
- Reporte de préstamos con exportación a CSV.

---

## 1. Requisitos

- Docker instalado.
- Bash (para ejecutar los scripts `.sh`).

No se usa `venv` ni instalación local de dependencias: todo corre dentro del contenedor.

---

## 2. Puesta en marcha

### 2.1. Levantar el entorno de desarrollo

```bash
./make_migrations.sh
```

Este script:

1. Construye la primer migracion inicial


```bash
./run_dev.sh
```

Este script:

1. Reconstruye la imagen Docker (`michi-biblioteca-django`).
2. Levanta el contenedor `michi-biblioteca-django-dev`.
3. Reinicia el contenedor, y el `entrypoint.sh`:
   - Crea usuarios y grupos iniciales.
   - Inicia el servidor Django en `0.0.0.0:8000`.

Luego podés entrar a:

```text
http://localhost:8000/
```

### 2.2. Cargar datos de prueba

Con el contenedor ya levantado:

```bash
./seed_demo_data.sh
```

Esto borra datos previos y vuelve a cargar:

- Categorías de libros (Novela, Tecnología, Historia, Fantasía, Infantil).
- Libros reales (Orwell, Eco, Dostoievski, Harari, Tolkien, etc.).
- Lectores de prueba.
- Préstamos en distintos estados (incluyendo libros con todos sus ejemplares prestados, lectores con préstamos atrasados, etc.).

### 2.3. Regenerar migraciones (solo si cambiás modelos)

Si modificás los modelos de Django, podés regenerar y revisar migraciones con:

```bash
./make_migrations.sh
```

Este script ejecuta dentro del contenedor:

- `python manage.py makemigrations biblioteca`
- `python manage.py showmigrations biblioteca`

> Normalmente no hace falta correrlo a mano si usás siempre `./run_dev.sh` cuando cambiás modelos.

---

## 3. Usuarios / Grupos creados automáticamente

El `entrypoint.sh` crea al arrancar el contenedor:

- **Admin**
  - usuario: `admin`
  - contraseña: `admin123`
  - superusuario.

- **Operador**
  - grupo: `Operador`
  - usuario: `operador`
  - contraseña: `operador123`

- **Supervisor**
  - grupo: `Supervisor`
  - usuario: `supervisor`
  - contraseña: `supervisor123`

### Permisos principales

- **Operador**
  - Puede crear préstamos.
  - Puede registrar devoluciones.
  - Puede marcar préstamos como robados.
  - Puede crear lectores desde el formulario de préstamo.
  - Puede ver listados (libros, préstamos).

- **Supervisor**
  - Todo lo anterior, más:
  - Puede crear/editar/eliminar **categorías**.
  - Puede crear/editar/eliminar **libros**.
  - Puede acceder a la pantalla de **Reporte de préstamos** y exportar CSV.

---

## 4. Paginación configurable

Todas las vistas de listados usan paginación:

- Listado de libros.
- Listado de préstamos.
- Listado de categorías.

Por defecto se muestran **20 elementos por página**, pero podés cambiar la cantidad con el querystring:

```text
?page_size=50
```

Ejemplos:

- `http://localhost:8000/libros/?page_size=10`
- `http://localhost:8000/prestamos/?page_size=100`
- `http://localhost:8000/categorias/?page_size=5`

Si no se envía `page_size` o es inválido, se usa el valor por defecto configurado en la vista (20).

---

## 5. Reporte de préstamos y exportación a CSV

Solo accesible para usuarios en el grupo **Supervisor**:

```text
http://localhost:8000/reporte-prestamos/
```

En esta pantalla se puede:

- Filtrar préstamos por:
  - Estado (PRESTADO, DEVUELTO, ATRASADO, ROBADO).
  - Categoría de libro.
  - Rango de fechas de préstamo (`fecha_desde`, `fecha_hasta`).
- Ver un resumen de cantidad de préstamos por estado.
- Ver la cantidad total de préstamos filtrados y cuántos están atrasados.
- Exportar el resultado a **CSV** (`?export=csv`).

### 5.1. Columnas del CSV

El CSV se genera desde la vista `reporte_prestamos` y contiene las siguientes columnas:

1. **ID**  
   Identificador del préstamo en el sistema.

2. **Libro**  
   Representación textual del libro asociado al préstamo (título y eventualmente otros datos definidos en `__str__` del modelo `Libro`).

3. **Lector**  
   Representación textual del lector (nombre, apellido y, según el modelo, DNI u otros datos que incluya `__str__` de `UsuarioLector`).

4. **Estado**  
   Estado actual del préstamo, en formato legible:
   - `PRESTADO`  → Libro actualmente en manos del lector.
   - `DEVUELTO`  → Libro devuelto en tiempo.
   - `ATRASADO`  → Libro no devuelto y con fecha de devolución estimada ya vencida.
   - `ROBADO`    → Marcado como no devuelto y dado por perdido.

5. **Fecha préstamo**  
   Fecha en que se registró el préstamo.

6. **Fecha estimada devolución**  
   Fecha límite pactada para devolver el libro.

7. **Fecha devolución real**  
   Fecha en que efectivamente se devolvió el libro.  
   - Vacío si el préstamo sigue en estado `PRESTADO`, `ATRASADO` o `ROBADO` (no hubo devolución).

8. **Categoría**  
   Nombre de la categoría del libro (por ejemplo: *Novela*, *Tecnología*, *Historia*, etc.).

El archivo CSV se genera en codificación **UTF-8**, separado por comas, listo para abrirse con Excel, LibreOffice o herramientas de análisis.

---

## 6. Auditoría simple de logs

El sistema registra en el log (nivel `INFO`) eventos relevantes, por ejemplo:

- Creación de préstamos.
- Registro de devoluciones.
- Marcado de préstamos como robados.
- Creación/edición/eliminación de categorías.
- Creación/edición/eliminación de libros.

Los logs se escriben en la salida estándar del contenedor (se pueden ver con `docker logs michi-biblioteca-django-dev`).

---

## 7. Tests

Para ejecutar los tests dentro del contenedor en ejecución:

```bash
docker exec -it michi-biblioteca-django-dev python manage.py test
```

Esto valida:

- Reglas del modelo `Prestamo` (fechas, capacidad de ejemplares, bloqueo por atrasos).
- Permisos de acceso al reporte de préstamos (solo supervisores).
- Flujo básico de creación de préstamos y registro de devoluciones.
