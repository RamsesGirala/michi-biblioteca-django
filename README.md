# Sistema de Biblioteca Michi

Pequeño sistema de gestión de biblioteca hecho con **Django** y **Docker**, pensado para practicar roles, préstamos, auditoría y paginación configurable.

## 1. Requisitos
- Docker instalado.
- Bash.

## 2. Puesta en marcha

### Iniciar BD
```
Ejecutar en terminal ./make_migrations.sh
```


### Levantar en desarrollo
```
Ejecutar en terminal ./run_dev.sh
```

### Cargar datos de prueba
```
Ejecutar en terminal ./seed_demo_data.sh
```

### Abrir en Navegador
```
http://localhost:8000/
```

### Usuarios / Grupos creados automáticamente
El `entrypoint.sh` crea:
- Usuario admin (`admin` / `admin123`)
- Grupo **Operador**, con usuario `operador` / `operador123`
- Grupo **Supervisor**, con usuario `supervisor` / `supervisor123`

## 3. Scripts

### run_dev.sh
Reconstruye imagen + levanta contenedor.

### make_migrations.sh
Actualiza las migraciones

### seed_demo_data.sh
Carga datos de demo.

## 4. Tests
```
docker exec -it michi-biblioteca-django-dev python manage.py test
```