#!/usr/bin/env bash
set -e

IMAGE_NAME="michi-biblioteca-django"
CONTAINER_NAME="michi-biblioteca-django-dev"

echo ">> (re)construyendo imagen Docker..."
docker build -t "${IMAGE_NAME}" .

# Si ya existe el contenedor, lo removemos
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}\$"; then
  echo ">> Eliminando contenedor previo ${CONTAINER_NAME}..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
fi

echo ">> Levantando contenedor ${CONTAINER_NAME}..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p 8000:8000 \
  "${IMAGE_NAME}"

echo ">> Listo. Django escuchando en http://localhost:8000"
echo "   Contenedor: ${CONTAINER_NAME}"
