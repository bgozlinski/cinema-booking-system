import stripe
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, ListView

from apps.booking.forms import BookingForm
from apps.booking.models import Booking, BookingStatus
from apps.booking.services import BookingError, cancel_booking, create_booking, start_checkout
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
            booking = create_booking(
                user=request.user,
                screening=screening,
                seats_count=form.cleaned_data["seats_count"],
            )
        except BookingError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"screening": screening, "form": form})
        try:
            checkout_url = start_checkout(booking=booking)
        except stripe.StripeError:
            messages.error(
                request,
                _("Płatność jest chwilowo niedostępna — spróbuj ponownie z poziomu rezerwacji."),
            )
            return redirect("booking:detail", pk=booking.pk)
        return redirect(checkout_url)


class BookingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Booking
    template_name = "booking/booking_detail.html"
    context_object_name = "booking"

    def get(self, request, *args, **kwargs):
        stripe_status = request.GET.get("stripe")
        if stripe_status == "success":
            messages.info(request, _("Płatność przyjęta — potwierdzenie rezerwacji wkrótce."))
        elif stripe_status == "cancelled":
            messages.warning(request, _("Płatność anulowana. Możesz spróbować ponownie."))
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # prefetch genres: the redesigned ticket lists them, so avoid a render-time query.
        return Booking.objects.select_related(
            "screening__movie", "screening__hall", "user"
        ).prefetch_related("screening__movie__genres")

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


class BookingCancelView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        booking = get_object_or_404(Booking, pk=pk, user=request.user.pk)
        try:
            cancel_booking(booking=booking)
        except BookingError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, _("Rezerwacja została anulowana."))
        return redirect("booking:my_bookings")


class BookingCheckoutView(LoginRequiredMixin, View):
    def post(self, request, pk: int):
        booking = get_object_or_404(Booking, pk=pk, user=request.user)
        if booking.status != BookingStatus.PENDING:
            messages.error(request, _("Tej rezerwacji nie można już opłacić."))
            return redirect("booking:detail", pk=booking.pk)
        try:
            checkout_url = start_checkout(booking=booking)
        except stripe.StripeError:
            messages.error(request, _("Płatność jest chwilowo niedostępna — spróbuj ponownie."))
            return redirect("booking:detail", pk=booking.pk)
        return redirect(checkout_url)
