from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path(
        "activate/sent/",
        views.ActivationSentView.as_view(),
        name="activation_sent",
    ),
    path(
        "activate/invalid/",
        views.ActivationInvalidView.as_view(),
        name="activation_invalid",
    ),
    path(
        "activate/resend/",
        views.ResendActivationView.as_view(),
        name="activation_resend",
    ),
    path(
        "activate/<uidb64>/<token>/",
        views.ActivateView.as_view(),
        name="activate",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
