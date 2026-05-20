from django.contrib import admin
from django.utils.html import format_html

from apps.cinema.models import Actor, Director, Genre, Hall, Movie


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ("name", "movies_count")
    search_fields = ("name",)

    @admin.display(description="movies")
    def movies_count(self, obj):
        return obj.movies.count()


@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ("name", "capacity", "screenings_count")
    search_fields = ("name",)

    @admin.display(description="screenings")
    def screenings_count(self, obj):
        return obj.screening_set.count()


@admin.register(Actor)
class ActorAdmin(admin.ModelAdmin):
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
    pass
