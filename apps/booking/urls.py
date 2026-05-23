from django.urls import path

from apps.booking.views import (
    BookingCancelView,
    BookingCheckoutView,
    BookingCreateView,
    BookingDetailView,
    MyBookingsView,
)

app_name = "booking"

urlpatterns = [
    path("screenings/<int:pk>/book/", BookingCreateView.as_view(), name="create"),
    path("bookings/<int:pk>/", BookingDetailView.as_view(), name="detail"),
    path("bookings/<int:pk>/cancel/", BookingCancelView.as_view(), name="cancel"),
    path("my-bookings/", MyBookingsView.as_view(), name="my_bookings"),
    path("bookings/<int:pk>/checkout/", BookingCheckoutView.as_view(), name="checkout"),
]
