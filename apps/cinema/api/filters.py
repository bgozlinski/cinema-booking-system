import django_filters

from apps.cinema.models import Movie


class MovieFilter(django_filters.FilterSet):
    genre = django_filters.NumberFilter(field_name="genres", lookup_expr="exact")
    release_date = django_filters.DateFromToRangeFilter(field_name="release_date")

    class Meta:
        model = Movie
        fields = ["genre", "release_date"]  # noqa: RUF012
