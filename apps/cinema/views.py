from django.views.generic import ListView

from apps.cinema.models import Movie


class MovieListView(ListView):
    model = Movie
    template_name = "cinema/movie_list.html"
    context_object_name = "movies"
    paginate_by = 12
