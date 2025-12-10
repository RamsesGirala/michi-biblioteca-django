#!/usr/bin/env bash
set -e

CONTAINER_NAME=michi-biblioteca-django-dev

echo ">> Ejecutando seed_demo_data en el contenedor ${CONTAINER_NAME}..."
docker exec -it "$CONTAINER_NAME" python manage.py seed_demo_data
echo ">> Listo. Datos de demo cargados."
