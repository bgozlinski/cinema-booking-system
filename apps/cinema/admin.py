from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import format_html

from apps.booking.models import Booking, BookingStatus
from apps.cinema.models import Actor, Director, Genre, Hall, Movie, Screening


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "movies_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_movies_count=Count("movies"))

    @admin.display(description="movies", ordering="_movies_count")
    def movies_count(self, obj):
        return obj._movies_count


@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity", "screenings_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_screenings_count=Count("screening"))

    @admin.display(description="screenings", ordering="_screenings_count")
    def screenings_count(self, obj):
        return obj._screenings_count


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "photo_thumbnail", "movies_count")
    search_fields = ("full_name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_movies_count=Count("movies"))

    @admin.display(description="photo")
    def photo_thumbnail(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.photo.url)

    @admin.display(description="movies", ordering="_movies_count")
    def movies_count(self, obj):
        return obj._movies_count


@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "photo_thumbnail", "movies_count")
    search_fields = ("full_name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_movies_count=Count("movies"))

    @admin.display(description="photo")
    def photo_thumbnail(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.photo.url)

    @admin.display(description="movies", ordering="_movies_count")
    def movies_count(self, obj):
        return obj._movies_count


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "release_date", "poster_thumbnail", "screenings_count", "genres_list")
    search_fields = ("title", "description", "directors__full_name")
    list_filter = ("genres", "release_date")
    filter_horizontal = ("genres", "actors", "directors")
    date_hierarchy = "release_date"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_screenings_count=Count("screenings", distinct=True))
            .prefetch_related("genres")
        )

    @admin.display(description="poster")
    def poster_thumbnail(self, obj):
        if not obj.poster:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.poster.url)

    @admin.display(description="screenings", ordering="_screenings_count")
    def screenings_count(self, obj):
        return obj._screenings_count

    @admin.display(description="genres")
    def genres_list(self, obj):
        names = sorted(g.name for g in obj.genres.all())
        return ", ".join(names) if names else "—"


class BookingInline(admin.TabularInline):
    model = Booking
    extra = 0
    fields = ("user", "seats_count", "status", "created_at")
    readonly_fields = ("user", "seats_count", "status", "created_at")
    can_delete = False
    show_change_link = True


@admin.register(Screening)
class ScreeningAdmin(admin.ModelAdmin):
    list_display = (
        "movie",
        "start_time",
        "hall",
        "price",
        "available_seats_display",
        "booked_seats_display",
    )
    list_filter = ("hall", "movie", "start_time")
    search_fields = ("movie__title",)
    date_hierarchy = "start_time"
    inlines = (BookingInline,)

    def get_queryset(self, request):
        now = timezone.now()
        return (
            super()
            .get_queryset(request)
            .select_related("movie", "hall")
            .annotate(
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
        )

    @admin.display(description="booked")
    def booked_seats_display(self, obj):
        return obj.booked_seats_count()

    @admin.display(description="available")
    def available_seats_display(self, obj):
        available = obj.available_seats_count()
        capacity = obj.hall.capacity
        ratio = available / capacity if capacity else 0
        if ratio > 0.5:
            color = "green"
        elif ratio >= 0.2:
            color = "orange"
        else:
            color = "red"
        return format_html('<b style="color: {};">{}</b>', color, available)
