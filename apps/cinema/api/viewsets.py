from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.cinema.api.filters import MovieFilter, ScreeningFilter
from apps.cinema.api.serializers import (
    ActorSerializer,
    DirectorSerializer,
    GenreSerializer,
    HallSerializer,
    MovieDetailSerializer,
    MovieListSerializer,
    ScreeningSerializer,
)
from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening
from apps.cinema.selectors import annotate_booked_count


class PublicReadViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]  # noqa: RUF012


class GenreViewSet(PublicReadViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer


class HallViewSet(PublicReadViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer


class ActorViewSet(PublicReadViewSet):
    queryset = Actor.objects.all()
    serializer_class = ActorSerializer


class DirectorViewSet(PublicReadViewSet):
    queryset = Director.objects.all()
    serializer_class = DirectorSerializer


class MovieViewSet(PublicReadViewSet):
    queryset = Movie.objects.all()
    filterset_class = MovieFilter
    search_fields = ["title"]  # noqa: RUF012

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MovieDetailSerializer
        return MovieListSerializer

    def get_queryset(self):
        qs = Movie.objects.prefetch_related("genres")
        if self.action == "retrieve":
            qs = qs.prefetch_related("actors", "directors")
        return qs


class ScreeningViewSet(PublicReadViewSet):
    queryset = Screening.objects.all()
    serializer_class = ScreeningSerializer
    filterset_class = ScreeningFilter

    def get_queryset(self):
        return annotate_booked_count(Screening.objects.select_related("movie", "hall")).order_by(
            "start_time"
        )
