from django.db.models import Min, Q
from django.utils import timezone
from django.views.generic import DetailView, ListView

from apps.cinema.models import Movie


class MovieListView(ListView):
    model = Movie
    template_name = "cinema/movie_list.html"
    context_object_name = "movies"
    paginate_by = 12

    def get_queryset(self):
        now = timezone.now()
        return (
            Movie.objects.annotate(
                next_screening_at=Min(
                    "screenings__start_time",
                    filter=Q(screenings__start_time__gte=now),
                )
            )
            .filter(next_screening_at__isnull=False)
            .prefetch_related("genres")
            .order_by("next_screening_at")
        )


class MovieDetailView(DetailView):
    model = Movie
    template_name = "cinema/movie_detail.html"
    context_object_name = "movie"
