from rest_framework.routers import SimpleRouter

from apps.booking.api.admin import AdminBookingViewSet

router = SimpleRouter()
router.register("bookings", AdminBookingViewSet, basename="admin-booking")

urlpatterns = router.urls
