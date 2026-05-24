from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAdminUser

from apps.cinema.api.serializers import (
    ActorSerializer,
    DirectorSerializer,
    GenreSerializer,
    HallSerializer,
)
from apps.cinema.api.validators import validate_image_upload
from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening


class AdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]  # noqa: RUF012


class AdminMovieSerializer(serializers.ModelSerializer):
    poster = serializers.ImageField(required=False, validators=[validate_image_upload])

    class Meta:
        model = Movie
        fields = (
            "id",
            "title",
            "description",
            "release_date",
            "duration_minutes",
            "poster",
            "trailer_url",
            "genres",
            "actors",
            "directors",
        )


class AdminScreeningSerializer(serializers.ModelSerializer):
    class Meta:
        model = Screening
        fields = ("id", "movie", "hall", "start_time", "price")


class AdminActorSerializer(ActorSerializer):
    photo = serializers.ImageField(required=False, validators=[validate_image_upload])


class AdminDirectorSerializer(DirectorSerializer):
    photo = serializers.ImageField(required=False, validators=[validate_image_upload])


class AdminGenreViewSet(AdminViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer


class AdminHallViewSet(AdminViewSet):
    queryset = Hall.objects.all()
    serializer_class = HallSerializer


class AdminActorViewSet(AdminViewSet):
    queryset = Actor.objects.all()
    serializer_class = AdminActorSerializer


class AdminDirectorViewSet(AdminViewSet):
    queryset = Director.objects.all()
    serializer_class = AdminDirectorSerializer


class AdminMovieViewSet(AdminViewSet):
    queryset = Movie.objects.prefetch_related("genres", "actors", "directors")
    serializer_class = AdminMovieSerializer


class AdminScreeningViewSet(AdminViewSet):
    queryset = Screening.objects.select_related("movie", "hall")
    serializer_class = AdminScreeningSerializer
