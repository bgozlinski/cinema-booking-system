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
