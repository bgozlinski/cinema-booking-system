from django.urls import path

from apps.accounts.api.views import RegisterView

app_name = "accounts_api"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
]
