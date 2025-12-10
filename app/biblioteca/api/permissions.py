from rest_framework.permissions import BasePermission
from biblioteca.views import es_operador, es_supervisor

class IsSupervisor(BasePermission):
    """
    Permite solo a usuarios en grupo Supervisor (o superuser).
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and es_supervisor(user))


class IsOperadorOrSupervisor(BasePermission):
    """
    Permite a Operador o Supervisor.
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (es_operador(user) or es_supervisor(user)))
