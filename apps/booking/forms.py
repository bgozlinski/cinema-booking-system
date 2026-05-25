from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from apps.cinema.models import Screening


class BookingForm(forms.Form):
    """Reservation input form (FR-07).

    Collects only ``seats_count``. The owning view (US-20) supplies user,
    screening, status and expires_at when persisting the Booking. The screening
    being booked is injected via ``__init__`` so the two server-side validations
    can run: seats within current availability, and the screening not in the past.
    The view re-checks availability inside ``select_for_update`` (US-20) — this
    form check is the user-facing pre-check, not the authoritative race guard.
    """

    seats_count = forms.IntegerField(
        label=_("Liczba miejsc"),
        min_value=1,
        max_value=10,
        error_messages={
            "required": _("Podaj liczbę miejsc."),
            "invalid": _("Podaj poprawną liczbę miejsc."),
            "min_value": _("Musisz zarezerwować co najmniej 1 miejsce."),
            "max_value": _("Maksymalnie możesz zarezerwować 10 miejsc."),
        },
        widget=forms.NumberInput(attrs={"min": 1, "max": 10, "class": "form-control"}),
    )

    def __init__(self, *args: Any, screening: Screening, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.screening = screening

    def clean_seats_count(self) -> int:
        seats_count: int = self.cleaned_data["seats_count"]
        available = self.screening.available_seats_count()
        if seats_count > available:
            raise forms.ValidationError(
                ngettext(
                    "Dostępnych jest tylko %(count)d miejsce — wybierz mniejszą liczbę.",
                    "Dostępnych jest tylko %(count)d miejsc — wybierz mniejszą liczbę.",
                    available,
                ),
                code="exceeds_available",
                params={"count": available},
            )
        return seats_count

    def clean(self) -> dict[str, Any] | None:
        cleaned_data = super().clean()
        if self.screening.is_in_past():
            raise forms.ValidationError(
                _("Seans już się rozpoczął — nie można zarezerwować miejsc."),
                code="screening_in_past",
            )
        return cleaned_data
