from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening
from apps.cinema.selectors import annotate_booked_count


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name")


class HallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = ("id", "name", "description", "capacity")


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = ("id", "full_name", "photo", "biography")


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = ("id", "full_name", "photo", "biography")


class MovieMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = ("id", "title", "poster")


class MovieScreeningSerializer(serializers.ModelSerializer):
    hall = HallSerializer(read_only=True)
    available_seats_count = serializers.SerializerMethodField()

    class Meta:
        model = Screening
        fields = ("id", "hall", "start_time", "price", "available_seats_count")

    def get_available_seats_count(self, obj) -> int:
        return obj.available_seats_count()


class MovieListSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)

    class Meta:
        model = Movie
        fields = ("id", "title", "release_date", "duration_minutes", "poster", "genres")


class MovieDetailSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    actors = ActorSerializer(many=True, read_only=True)
    directors = DirectorSerializer(many=True, read_only=True)
    upcoming_screenings = serializers.SerializerMethodField()

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
            "upcoming_screenings",
        )

    @extend_schema_field(MovieScreeningSerializer(many=True))
    def get_upcoming_screenings(self, obj):
        qs = annotate_booked_count(
            obj.screenings.filter(start_time__gte=timezone.now())
            .select_related("hall")
            .order_by("start_time")
        )
        return MovieScreeningSerializer(qs, many=True).data


class ScreeningSerializer(serializers.ModelSerializer):
    movie = MovieMiniSerializer(read_only=True)
    hall = HallSerializer(read_only=True)
    available_seats_count = serializers.SerializerMethodField()

    class Meta:
        model = Screening
        fields = ("id", "movie", "hall", "start_time", "price", "available_seats_count")

    def get_available_seats_count(self, obj) -> int:
        return obj.available_seats_count()
