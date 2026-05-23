from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.booking.forms import BookingForm
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
