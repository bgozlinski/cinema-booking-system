import datetime
from collections import OrderedDict
from datetime import time, timedelta

from django.contrib import messages
from django.db.models import Min, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.views.generic import DetailView, ListView, TemplateView

from apps.booking.models import BookingStatus
from apps.cinema.forms import MovieFilterForm
from apps.cinema.models import Movie, Screening
from apps.cinema.utils import youtube_embed_url


def _annotate_booked_count(qs):
    """Annotates _annotated_booked_count on Screening queryset.

    Eliminates N+1 from is_available() / available_seats_count() calls in
    templates iterating screenings (US-18 perf concern).
    """
    now = timezone.now()
    return qs.annotate(
        _annotated_booked_count=Coalesce(
            Sum(
                "bookings__seats_count",
                filter=(
                    Q(bookings__status=BookingStatus.CONFIRMED)
                    | Q(
                        bookings__status=BookingStatus.PENDING,
                        bookings__expires_at__gt=now,
                    )
                ),
            ),
            0,
        )
    )


class MovieListView(ListView):
    model = Movie
    template_name = "cinema/movie_list.html"
    context_object_name = "movies"
    paginate_by = 12

    def get_queryset(self):
        now = timezone.now()
        qs = (
            Movie.objects.annotate(
                next_screening_at=Min(
                    "screenings__start_time",
                    filter=Q(screenings__start_time__gte=now),
                )
            )
            .filter(next_screening_at__isnull=False)
            .prefetch_related("genres")
        )

        form = MovieFilterForm(self.request.GET or None)
        if form.is_valid():
            if q := form.cleaned_data.get("q"):
                qs = qs.filter(title__icontains=q)
            if genre := form.cleaned_data.get("genre"):
                qs = qs.filter(genres=genre)
            if d := form.cleaned_data.get("date"):
                day_start = timezone.make_aware(datetime.datetime.combine(d, time.min))
                day_end = day_start + timedelta(days=1)
                qs = qs.filter(
                    screenings__start_time__gte=day_start,
                    screenings__start_time__lt=day_end,
                ).distinct()

        return qs.order_by("next_screening_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filter_form"] = MovieFilterForm(self.request.GET or None)
        return ctx


class MovieDetailView(DetailView):
    model = Movie
    template_name = "cinema/movie_detail.html"
    context_object_name = "movie"

    def get_queryset(self):
        return Movie.objects.prefetch_related("genres", "actors", "directors")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["trailer_embed_url"] = youtube_embed_url(self.object.trailer_url)
        ctx["upcoming_screenings"] = _annotate_booked_count(
            self.object.screenings.filter(start_time__gte=timezone.now())
            .select_related("hall")
            .order_by("start_time")
        )
        return ctx


class ScreeningListView(TemplateView):
    template_name = "cinema/screening_list.html"

    def _resolve_date(self):
        """Parse ?date= and clamp to today..today+30. Returns (effective_date, was_clamped, raw_input)."""
        today = timezone.localdate()
        max_date = today + timedelta(days=30)
        raw = self.request.GET.get("date", "")
        if not raw:
            return today, False, ""
        try:
            requested = datetime.date.fromisoformat(raw)
        except ValueError:
            return today, True, raw
        if requested < today:
            return today, True, raw
        if requested > max_date:
            return max_date, True, raw
        return requested, False, raw

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        effective, clamped, _raw = self._resolve_date()
        if clamped:
            messages.warning(
                self.request,
                f"Data poza zakresem; pokazano dla {effective.isoformat()}.",
            )
        day_start = timezone.make_aware(datetime.datetime.combine(effective, time.min))
        day_end = day_start + timedelta(days=1)

        screenings = _annotate_booked_count(
            Screening.objects.filter(start_time__gte=day_start, start_time__lt=day_end)
            .select_related("movie", "hall")
            .prefetch_related("movie__genres")
            .order_by("movie__title", "start_time")
        )

        grouped: OrderedDict = OrderedDict()
        for s in screenings:
            grouped.setdefault(s.movie, []).append(s)
        movie_groups = sorted(grouped.items(), key=lambda item: item[1][0].start_time)

        ctx["effective_date"] = effective
        ctx["today"] = timezone.localdate()
        ctx["max_date"] = timezone.localdate() + timedelta(days=30)
        ctx["movie_groups"] = movie_groups
        return ctx
