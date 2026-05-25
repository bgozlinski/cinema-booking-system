from typing import TYPE_CHECKING, Any, cast

from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.api.serializers import (
    RegisterResponseSerializer,
    RegisterSerializer,
    UserSerializer,
)
from apps.accounts.emails import send_activation_email

if TYPE_CHECKING:
    from apps.accounts.models import User


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]  # noqa: RUF012
    serializer_class = RegisterSerializer
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    throttle_scope = "auth"

    @extend_schema(
        summary="Register a new account",
        description="Creates an inactive user and sends an activation email. Returns no JWT — activate via the emailed link, then obtain a token at /auth/token/.",
        responses=RegisterResponseSerializer,
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_activation_email(user, request._request)
        data = {"user": UserSerializer(user).data, "detail": "Activation email sent."}
        return Response(data, status=201)


class AuthTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [ScopedRateThrottle]  # noqa: RUF012
    throttle_scope = "auth"


class MeView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]  # noqa: RUF012
    serializer_class = UserSerializer

    def get_object(self) -> "User":
        return cast("User", self.request.user)
