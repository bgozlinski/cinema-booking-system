from django.urls import path

from .views import MovieDetailView, MovieListView, ScreeningListView

app_name = "cinema"

urlpatterns = [
    path("", MovieListView.as_view(), name="home"),
    path("movies/", MovieListView.as_view(), name="movie_list"),
    path("movies/<int:pk>/", MovieDetailView.as_view(), name="movie_detail"),
    path("screenings/", ScreeningListView.as_view(), name="screening_list"),
]
