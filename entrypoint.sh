#!/bin/bash
set -e

echo ">> Aplicando migraciones..."
python manage.py migrate --noinput

echo ">> Creando grupos y usuarios iniciales..."
python manage.py shell << 'EOF'
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

# Grupos
operador_g, _ = Group.objects.get_or_create(name="Operador")
supervisor_g, _ = Group.objects.get_or_create(name="Supervisor")

# Admin
if not User.objects.filter(username="admin").exists():
    User.objects.create_superuser("admin", "admin@example.com", "admin123")

# Operador
if not User.objects.filter(username="operador").exists():
    u = User.objects.create_user("operador", password="operador123")
    u.groups.add(operador_g)

# Supervisor
if not User.objects.filter(username="supervisor").exists():
    u = User.objects.create_user("supervisor", password="supervisor123")
    u.groups.add(supervisor_g)

EOF

echo ">> Iniciando servidor..."
exec python manage.py runserver 0.0.0.0:8000
