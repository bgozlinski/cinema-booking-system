from typing import Any

from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "is_staff")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "password", "first_name", "last_name")
        extra_kwargs = {  # noqa: RUF012
            "first_name": {"required": False},
            "last_name": {"required": False},
        }

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value

    def create(self, validated_data: dict[str, Any]) -> Any:
        return User.objects.create_user(is_active=False, **validated_data)


class RegisterResponseSerializer(serializers.Serializer):
    user = UserSerializer()
    detail = serializers.CharField()
