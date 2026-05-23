from django.urls import path

from apps.booking.views import BookingCreateView

app_name = "booking"

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
]
