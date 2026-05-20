from django.contrib import admin

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
    pass


@admin.register(Director)
class DirectorAdmin(admin.ModelAdmin):
    pass


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    pass
