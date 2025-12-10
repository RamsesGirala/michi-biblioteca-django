#!/usr/bin/env bash
set -e

IMAGE_NAME="michi-biblioteca-django"

echo ">> Verificando imagen ${IMAGE_NAME}..."
if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  echo ">> Imagen ${IMAGE_NAME} no encontrada. Construyendo..."
  docker build -t "${IMAGE_NAME}" .
fi

echo ">> Generando migraciones para 'biblioteca' usando un contenedor temporal..."
docker run --rm \
  -v "$(pwd)/app:/app" \
  -w /app \
  "${IMAGE_NAME}" \
  python manage.py makemigrations biblioteca

echo ">> Listado de migraciones de 'biblioteca':"
docker run --rm \
  -v "$(pwd)/app:/app" \
  -w /app \
  "${IMAGE_NAME}" \
  python manage.py showmigrations biblioteca
