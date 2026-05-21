from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from apps.cinema.models import Actor, Director, Genre, Hall, Movie


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

    @admin.display(description="photo")
    def photo_thumbnail(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.photo.url)

    @admin.display(description="movies")
    def movies_count(self, obj):
        return obj.movies.count()


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "release_date", "poster_thumbnail", "screenings_count", "genres_list")
    search_fields = ("title", "description", "directors__full_name")
    list_filter = ("genres", "release_date")
    filter_horizontal = ("genres", "actors", "directors")
    date_hierarchy = "release_date"

    @admin.display(description="poster")
    def poster_thumbnail(self, obj):
        if not obj.poster:
            return "—"
        return format_html('<img src="{}" style="height:60px;" />', obj.poster.url)

    @admin.display(description="screenings")
    def screenings_count(self, obj):
        return obj.screenings.count()

    @admin.display(description="genres")
    def genres_list(self, obj):
        names = list(obj.genres.values_list("name", flat=True).order_by("name"))
        if not names:
            return "—"
        return ", ".join(names)
