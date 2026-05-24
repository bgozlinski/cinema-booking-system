from rest_framework import serializers

from apps.booking.models import Booking
from apps.cinema.api.serializers import HallSerializer, MovieMiniSerializer
from apps.cinema.models import Screening


class BookingScreeningSerializer(serializers.ModelSerializer):
    movie = MovieMiniSerializer(read_only=True)
    hall = HallSerializer(read_only=True)

    class Meta:
        model = Screening
        fields = ("id", "movie", "hall", "start_time", "price")


class BookingSerializer(serializers.ModelSerializer):
    screening = BookingScreeningSerializer(read_only=True)
    total_price = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = Booking
        fields = (
            "id",
            "screening",
            "seats_count",
            "status",
            "total_price",
            "created_at",
            "expires_at",
        )
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    screening_id = serializers.PrimaryKeyRelatedField(
        queryset=Screening.objects.all(), source="screening"
    )
    seats_count = serializers.IntegerField(min_value=1, max_value=10)


class BookingCreateResponseSerializer(serializers.Serializer):
    booking = BookingSerializer()
    checkout_url = serializers.CharField(allow_null=True)
    detail = serializers.CharField(required=False)
