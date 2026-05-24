import datetime
from datetime import time, timedelta

import django_filters
from django.utils import timezone

from apps.cinema.models import Movie, Screening


class MovieFilter(django_filters.FilterSet):
    genre = django_filters.NumberFilter(field_name="genres", lookup_expr="exact")
    release_date = django_filters.DateFromToRangeFilter(field_name="release_date")

    class Meta:
        model = Movie
        fields = ["genre", "release_date"]  # noqa: RUF012


class ScreeningFilter(django_filters.FilterSet):
    date = django_filters.DateFilter(method="filter_date")
    movie = django_filters.NumberFilter(field_name="movie__id")
    hall = django_filters.NumberFilter(field_name="hall__id")

    class Meta:
        model = Screening
        fields = ["date", "movie", "hall"]  # noqa: RUF012

    def filter_date(self, queryset, name, value):
        day_start = timezone.make_aware(datetime.datetime.combine(value, time.min))
        day_end = day_start + timedelta(days=1)
        return queryset.filter(start_time__gte=day_start, start_time__lt=day_end)
