from rest_framework import serializers
from biblioteca.models import CategoriaLibro, Libro, UsuarioLector, Prestamo


class CategoriaLibroSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaLibro
        fields = ["id", "nombre", "descripcion", "activo"]
        read_only_fields = ["activo"]
        extra_kwargs = {
            "nombre": {"required": True},
            "descripcion": {"required": False, "allow_blank": True},
        }


class LibroSerializer(serializers.ModelSerializer):
    categoria = CategoriaLibroSerializer(read_only=True)
    categoria_id = serializers.PrimaryKeyRelatedField(
        source="categoria",
        queryset=CategoriaLibro.objects.all(),
        write_only=True,
    )

    class Meta:
        model = Libro
        fields = [
            "id",
            "titulo",
            "autor",
            "isbn",
            "categoria",
            "categoria_id",
            "ejemplares_totales",
            "ejemplares_disponibles",
            "activo",
        ]
        # solo 'activo' lo dejamos de solo lectura (si querés)
        read_only_fields = ["activo"]
        extra_kwargs = {
            # obligatorios
            "titulo": {"required": True},
            "autor": {"required": True},
            "ejemplares_totales": {"required": True},
            "ejemplares_disponibles": {"required": True},
            # 'categoria' viene por categoria_id
            "categoria": {"required": False},
            # opcional
            "isbn": {"required": False, "allow_blank": True},
        }

class UsuarioLectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = UsuarioLector
        fields = ["id", "nombre", "apellido", "dni", "email", "telefono", "activo"]

class PrestamoSerializer(serializers.ModelSerializer):
    # libro: nested solo lectura
    libro = LibroSerializer(read_only=True)
    libro_id = serializers.PrimaryKeyRelatedField(
        source="libro",
        queryset=Libro.objects.all(),
        write_only=True,
        required=True,
    )

    # lector existente
    lector = UsuarioLectorSerializer(read_only=True)
    lector_id = serializers.PrimaryKeyRelatedField(
        source="lector",
        queryset=UsuarioLector.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    # datos para lector nuevo (opcionales, con regla email/teléfono)
    lector_nuevo_nombre = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    lector_nuevo_apellido = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    lector_nuevo_dni = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    lector_nuevo_email = serializers.EmailField(
        write_only=True, required=False, allow_blank=True
    )
    lector_nuevo_telefono = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    class Meta:
        model = Prestamo
        fields = [
            "id",
            "libro",
            "libro_id",
            "lector",
            "lector_id",
            "lector_nuevo_nombre",
            "lector_nuevo_apellido",
            "lector_nuevo_dni",
            "lector_nuevo_email",
            "lector_nuevo_telefono",
            "fecha_prestamo",
            "fecha_devolucion_estimada",
            "fecha_devolucion_real",
            "estado",
            "comentarios",
            "creado_por",
        ]
        read_only_fields = ["creado_por", "estado", "fecha_devolucion_real"]
        extra_kwargs = {
            "fecha_prestamo": {"required": True},
            "fecha_devolucion_estimada": {"required": True},
            "comentarios": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        """
        Reglas:
        - Debe venir lector_id OR datos de lector nuevo.
        - Si hay lector_id y también datos de lector nuevo -> error.
        - Si es lector nuevo: email o teléfono al menos uno.
        """
        attrs = super().validate(attrs)

        lector = attrs.get("lector")
        nuevo_nombre = (attrs.get("lector_nuevo_nombre") or "").strip()
        nuevo_apellido = (attrs.get("lector_nuevo_apellido") or "").strip()
        nuevo_dni = (attrs.get("lector_nuevo_dni") or "").strip()
        nuevo_email = (attrs.get("lector_nuevo_email") or "").strip()
        nuevo_telefono = (attrs.get("lector_nuevo_telefono") or "").strip()

        hay_datos_nuevo = any(
            [nuevo_nombre, nuevo_apellido, nuevo_dni, nuevo_email, nuevo_telefono]
        )

        # 1) No se permite mezclar lector existente + datos de lector nuevo
        if lector is not None and hay_datos_nuevo:
            raise serializers.ValidationError(
                "No podés enviar lector_id y datos de lector nuevo al mismo tiempo."
            )

        # 2) Debe haber o lector existente o datos de lector nuevo
        if lector is None and not hay_datos_nuevo:
            raise serializers.ValidationError(
                "Debés indicar lector_id o los datos de un lector nuevo."
            )

        # 3) Si es lector nuevo: email o teléfono al menos uno
        if lector is None and hay_datos_nuevo:
            if not (nuevo_email or nuevo_telefono):
                raise serializers.ValidationError(
                    "Para un lector nuevo debés informar al menos email o teléfono."
                )

        return attrs

    def create(self, validated_data):
        """
        Crea lector nuevo si hace falta y luego crea el préstamo.
        """
        nuevo_nombre = (validated_data.pop("lector_nuevo_nombre", "") or "").strip()
        nuevo_apellido = (validated_data.pop("lector_nuevo_apellido", "") or "").strip()
        nuevo_dni = (validated_data.pop("lector_nuevo_dni", "") or "").strip()
        nuevo_email = (validated_data.pop("lector_nuevo_email", "") or "").strip()
        nuevo_telefono = (validated_data.pop("lector_nuevo_telefono", "") or "").strip()

        lector = validated_data.get("lector")

        if lector is None:
            lector = UsuarioLector.objects.create(
                nombre=nuevo_nombre,
                apellido=nuevo_apellido,
                dni=nuevo_dni,
                email=nuevo_email,
                telefono=nuevo_telefono,
                activo=True,
            )
            validated_data["lector"] = lector

        prestamo = Prestamo.objects.create(**validated_data)
        return prestamo
