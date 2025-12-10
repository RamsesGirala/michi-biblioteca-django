from django import forms
from .models import Prestamo, UsuarioLector, CategoriaLibro, Libro


class PrestamoForm(forms.ModelForm):
    # 👇 lector explícito y NO requerido ⇒ el <select> ya no tiene "required"
    lector = forms.ModelChoiceField(
        queryset=UsuarioLector.objects.filter(activo=True),
        required=False,
        label="Lector",
    )

    # extras para crear lector en el mismo formulario
    crear_nuevo_lector = forms.BooleanField(
        required=False,
        label="Crear nuevo lector",
        help_text="Tildá esta opción si el lector no existe todavía.",
    )
    nombre_lector = forms.CharField(
        required=False,
        label="Nombre del nuevo lector",
    )
    apellido_lector = forms.CharField(
        required=False,
        label="Apellido del nuevo lector",
    )
    dni_lector = forms.CharField(
        required=False,
        label="DNI del nuevo lector",
    )

    class Meta:
        model = Prestamo
        fields = [
            "libro",
            "lector",  # lector existente (ahora viene de arriba, required=False)
            "fecha_prestamo",
            "fecha_devolucion_estimada",
            "comentarios",
        ]
        widgets = {
            "fecha_prestamo": forms.DateInput(attrs={"type": "date"}),
            "fecha_devolucion_estimada": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        crear_nuevo = cleaned_data.get("crear_nuevo_lector")
        lector = cleaned_data.get("lector")
        nombre = cleaned_data.get("nombre_lector")
        apellido = cleaned_data.get("apellido_lector")
        dni = cleaned_data.get("dni_lector")

        if crear_nuevo:
            # si se tilda "crear nuevo lector", validamos los campos nuevos
            if not nombre:
                self.add_error("nombre_lector", "Para crear un nuevo lector ingresá el nombre.")
            if not apellido:
                self.add_error("apellido_lector", "Para crear un nuevo lector ingresá el apellido.")
            if not dni:
                self.add_error("dni_lector", "Para crear un nuevo lector ingresá el DNI.")
        else:
            # si NO se crea nuevo, debe haber un lector elegido
            if lector is None:
                self.add_error(
                    "lector",
                    "Debés seleccionar un lector existente o marcar 'Crear nuevo lector'.",
                )

        return cleaned_data

class CategoriaLibroForm(forms.ModelForm):
    class Meta:
        model = CategoriaLibro
        fields = ["nombre", "activo"]

class LibroForm(forms.ModelForm):
    class Meta:
        model = Libro
        fields = [
            "titulo",
            "autor",
            "categoria",
            "ejemplares_totales",
            "ejemplares_disponibles",
        ]