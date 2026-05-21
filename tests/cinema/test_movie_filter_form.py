"""Unit tests for MovieFilterForm (US-12 / FR-02)."""

from datetime import date

import pytest

from apps.cinema.forms import MovieFilterForm
from tests.cinema.factories import GenreFactory

pytestmark = pytest.mark.django_db


class TestMovieFilterForm:
    def test_empty_data_is_valid_with_empty_values(self):
        form = MovieFilterForm(data={})
        assert form.is_valid()
        assert form.cleaned_data["q"] == ""
        assert form.cleaned_data["genre"] is None
        assert form.cleaned_data["date"] is None

    def test_q_field_accepts_text(self):
        form = MovieFilterForm(data={"q": "Matrix"})
        assert form.is_valid()
        assert form.cleaned_data["q"] == "Matrix"

    def test_genre_field_accepts_valid_pk(self):
        genre = GenreFactory(name="Drama")
        form = MovieFilterForm(data={"genre": str(genre.pk)})
        assert form.is_valid()
        assert form.cleaned_data["genre"] == genre

    def test_date_field_accepts_iso_date_string(self):
        form = MovieFilterForm(data={"date": "2026-05-23"})
        assert form.is_valid()
        assert form.cleaned_data["date"] == date(2026, 5, 23)

    def test_date_field_rejects_malformed_value(self):
        form = MovieFilterForm(data={"date": "not-a-date"})
        assert not form.is_valid()
        assert "date" in form.errors

    def test_genre_field_rejects_nonexistent_pk(self):
        form = MovieFilterForm(data={"genre": "99999"})
        assert not form.is_valid()
        assert "genre" in form.errors
