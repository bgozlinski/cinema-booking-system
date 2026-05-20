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
