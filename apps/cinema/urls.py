from django.urls import path

from .views import MovieListView

app_name = "cinema"

urlpatterns = [
    path("", MovieListView.as_view(), name="home"),
    path("movies/", MovieListView.as_view(), name="movie_list"),
]
