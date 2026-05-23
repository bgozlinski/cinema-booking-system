from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from apps.booking.forms import BookingForm
from apps.booking.models import Booking
from apps.booking.services import BookingError, create_booking
from apps.cinema.models import Screening


class BookingCreateView(LoginRequiredMixin, View):
    template_name = "booking/booking_form.html"

    def _get_screening(self, pk: int) -> Screening:
        return get_object_or_404(Screening.objects.select_related("movie", "hall"), pk=pk)

    def get(self, request, pk: int):
        screening = self._get_screening(pk)
        form = BookingForm(screening=screening)
        return render(request, self.template_name, {"screening": screening, "form": form})

    def post(self, request, pk: int):
        screening = self._get_screening(pk)
        form = BookingForm(request.POST, screening=screening)
        if not form.is_valid():
            return render(request, self.template_name, {"screening": screening, "form": form})
        try:
            _booking, checkout_url = create_booking(
                user=request.user,
                screening=screening,
                seats_count=form.cleaned_data["seats_count"],
            )
        except BookingError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"screening": screening, "form": form})

        messages.success(request, "Rezerwacja utworzona (PENDING) — dokończ płatność.")
        return redirect(checkout_url)


class BookingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Booking
    template_name = "booking/booking_detail.html"
    context_object_name = "booking"

    def get_queryset(self):
        return Booking.objects.select_related("screening__movie", "screening__hall", "user")

    def get_object(self, queryset=None):
        if not hasattr(self, "_booking"):
            self._booking = super().get_object(queryset)
        return self._booking

    def test_func(self) -> bool:
        booking = self.get_object()
        return self.request.user == booking.user or self.request.user.is_staff


class MyBookingsView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = "booking/my_bookings.html"
    context_object_name = "bookings"

    def _active_tab(self) -> str:
        return "history" if self.request.GET.get("tab") == "history" else "upcoming"

    def get_queryset(self):
        qs = Booking.objects.filter(user=self.request.user.pk).select_related(
            "screening__movie", "screening__hall"
        )
        now = timezone.now()
        if self._active_tab() == "history":
            qs = qs.filter(screening__start_time__lt=now)
        else:
            qs = qs.filter(screening__start_time__gte=now)
        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["active_tab"] = self._active_tab()
        return ctx
