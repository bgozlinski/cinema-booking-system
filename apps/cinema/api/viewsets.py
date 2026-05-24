from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from apps.cinema.api.serializers import (
    ActorSerializer,
    DirectorSerializer,
    GenreSerializer,
    HallSerializer,
)
from apps.cinema.models import Actor, Director, Genre, Hall


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
