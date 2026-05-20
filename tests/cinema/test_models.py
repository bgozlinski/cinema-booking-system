import datetime as dt

import pytest
from django.db import IntegrityError

from apps.cinema.models import Genre
from tests.cinema.factories import GenreFactory


@pytest.mark.django_db
def test_genre_str_returns_name():
    genre = GenreFactory(name="Drama")
    assert str(genre) == "Drama"


@pytest.mark.django_db
def test_genre_name_unique_constraint():
    Genre.objects.create(name="Comedy")
    with pytest.raises(IntegrityError):
        Genre.objects.create(name="Comedy")


@pytest.mark.django_db
def test_genre_meta_ordering_by_name():
    GenreFactory(name="Zombie")
    GenreFactory(name="Action")
    GenreFactory(name="Mystery")

    names = list(Genre.objects.values_list("name", flat=True))
    assert names == ["Action", "Mystery", "Zombie"]


@pytest.mark.django_db
def test_genre_name_max_length_50():
    field = Genre._meta.get_field("name")
    assert field.max_length == 50


@pytest.mark.django_db
def test_actor_str_returns_full_name():
    from apps.cinema.models import Actor

    actor = Actor.objects.create(full_name="Anna Kowalska")
    assert str(actor) == "Anna Kowalska"


@pytest.mark.django_db
def test_actor_photo_blank_allowed():
    from apps.cinema.models import Actor

    actor = Actor.objects.create(full_name="Jan Nowak")
    assert actor.photo.name == ""


@pytest.mark.django_db
def test_actor_biography_blank_allowed():
    from apps.cinema.models import Actor

    actor = Actor.objects.create(full_name="Piotr Wiśniewski")
    assert actor.biography == ""


@pytest.mark.django_db
def test_director_str_returns_full_name():
    from apps.cinema.models import Director

    director = Director.objects.create(full_name="Andrzej Wajda")
    assert str(director) == "Andrzej Wajda"


@pytest.mark.django_db
def test_hall_str_returns_name():
    from apps.cinema.models import Hall

    hall = Hall.objects.create(name="Sala A")
    assert str(hall) == "Sala A"


@pytest.mark.django_db
def test_hall_name_unique_constraint():
    from apps.cinema.models import Hall

    Hall.objects.create(name="Sala B")
    with pytest.raises(IntegrityError):
        Hall.objects.create(name="Sala B")


@pytest.mark.django_db
def test_hall_capacity_default_100():
    from apps.cinema.models import Hall

    hall = Hall.objects.create(name="Sala C")
    assert hall.capacity == 100


@pytest.mark.django_db
def test_hall_description_blank_allowed():
    from apps.cinema.models import Hall

    hall = Hall.objects.create(name="Sala E")
    assert hall.description == ""


@pytest.mark.django_db
def test_hall_capacity_validator_rejects_zero():
    from django.core.exceptions import ValidationError

    from apps.cinema.models import Hall

    hall = Hall(name="Sala D", capacity=0)
    with pytest.raises(ValidationError):
        hall.full_clean()


@pytest.mark.django_db
def test_movie_str_returns_title():
    from apps.cinema.models import Movie

    movie = Movie.objects.create(
        title="Inception",
        description="Dream within a dream.",
        release_date=dt.date(2010, 7, 16),
        duration_minutes=148,
    )
    assert str(movie) == "Inception"


@pytest.mark.django_db
def test_movie_duration_validator_rejects_zero():
    from django.core.exceptions import ValidationError

    from apps.cinema.models import Movie

    movie = Movie(
        title="Bad Movie",
        description="x",
        release_date=dt.date(2024, 1, 1),
        duration_minutes=0,
    )
    with pytest.raises(ValidationError):
        movie.full_clean()


@pytest.mark.django_db
def test_movie_poster_blank_allowed():
    from apps.cinema.models import Movie

    movie = Movie.objects.create(
        title="No Poster",
        description="x",
        release_date=dt.date(2024, 1, 1),
        duration_minutes=90,
    )
    assert movie.poster.name == ""


@pytest.mark.django_db
def test_movie_trailer_url_blank_allowed():
    from apps.cinema.models import Movie

    movie = Movie.objects.create(
        title="No Trailer",
        description="x",
        release_date=dt.date(2024, 1, 1),
        duration_minutes=90,
    )
    assert movie.trailer_url == ""


@pytest.mark.django_db
def test_movie_genres_m2m_works():
    from tests.cinema.factories import MovieFactory

    drama = GenreFactory(name="Drama")
    comedy = GenreFactory(name="Comedy")
    movie = MovieFactory(genres=[drama, comedy])

    assert drama in movie.genres.all()
    assert comedy in movie.genres.all()
    assert movie in drama.movies.all()  # reverse related_name


@pytest.mark.django_db
def test_movie_actors_m2m_works():
    from tests.cinema.factories import ActorFactory, MovieFactory

    actor1 = ActorFactory(full_name="Actor One")
    actor2 = ActorFactory(full_name="Actor Two")
    movie = MovieFactory(actors=[actor1, actor2])

    assert actor1 in movie.actors.all()
    assert actor2 in movie.actors.all()


@pytest.mark.django_db
def test_movie_directors_m2m_works():
    from tests.cinema.factories import DirectorFactory, MovieFactory

    dir1 = DirectorFactory(full_name="Director One")
    movie = MovieFactory(directors=[dir1])

    assert dir1 in movie.directors.all()


@pytest.mark.django_db
def test_movie_meta_ordering_release_date_desc_then_title():
    from apps.cinema.models import Movie
    from tests.cinema.factories import MovieFactory

    MovieFactory(title="Older", release_date=dt.date(2020, 1, 1))
    MovieFactory(title="Newer A", release_date=dt.date(2024, 6, 1))
    MovieFactory(title="Newer B", release_date=dt.date(2024, 6, 1))

    titles = list(Movie.objects.values_list("title", flat=True))
    # Same release_date → secondary sort by title ascending
    assert titles == ["Newer A", "Newer B", "Older"]
