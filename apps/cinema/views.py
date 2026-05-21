import datetime
from datetime import time, timedelta

from django.db.models import Min, Q
from django.utils import timezone
from django.views.generic import DetailView, ListView

from apps.cinema.forms import MovieFilterForm
from apps.cinema.models import Movie
from apps.cinema.utils import youtube_embed_url


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
        ctx["upcoming_screenings"] = (
            self.object.screenings.filter(start_time__gte=timezone.now())
            .select_related("hall")
            .order_by("start_time")
        )
        return ctx
