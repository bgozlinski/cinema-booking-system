from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("auth/", include("apps.accounts.api.urls")),
    path("", include("apps.cinema.api.urls")),
    path("", include("apps.booking.api.urls")),
    path("admin/", include("apps.cinema.api.admin_urls")),
    path("admin/", include("apps.booking.api.admin_urls")),
]
