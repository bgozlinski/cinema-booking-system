from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.api.views import AuthTokenObtainPairView, RegisterView

app_name = "accounts_api"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", AuthTokenObtainPairView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]
