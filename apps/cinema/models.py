from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class Genre(models.Model):
    name = models.CharField(_("name"), max_length=50, unique=True)

    class Meta:
        verbose_name = _("genre")
        verbose_name_plural = _("genres")
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Actor(models.Model):
    full_name = models.CharField(_("full name"), max_length=150)
    photo = models.ImageField(_("photo"), upload_to="actors/", blank=True)
    biography = models.TextField(_("biography"), blank=True)

    class Meta:
        verbose_name = _("actor")
        verbose_name_plural = _("actors")
        ordering = ("full_name",)

    def __str__(self) -> str:
        return self.full_name


class Director(models.Model):
    full_name = models.CharField(_("full name"), max_length=150)
    photo = models.ImageField(_("photo"), upload_to="directors/", blank=True)
    biography = models.TextField(_("biography"), blank=True)

    class Meta:
        verbose_name = _("director")
        verbose_name_plural = _("directors")
        ordering = ("full_name",)

    def __str__(self) -> str:
        return self.full_name


class Hall(models.Model):
    name = models.CharField(_("name"), max_length=50, unique=True)
    description = models.TextField(
        _("description"),
        blank=True,
    )
    capacity = models.PositiveIntegerField(
        _("capacity"),
        default=100,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = _("hall")
        verbose_name_plural = _("halls")
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Movie(models.Model):
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"))
    release_date = models.DateField(_("release date"))
    duration_minutes = models.PositiveIntegerField(
        _("duration (minutes)"),
        validators=[MinValueValidator(1)],
    )
    poster = models.ImageField(_("poster"), upload_to="posters/", blank=True)
    trailer_url = models.URLField(_("trailer URL"), blank=True)
    genres = models.ManyToManyField(Genre, related_name="movies", verbose_name=_("genres"))
    actors = models.ManyToManyField(Actor, related_name="movies", verbose_name=_("actors"))
    directors = models.ManyToManyField(Director, related_name="movies", verbose_name=_("directors"))

    class Meta:
        verbose_name = _("movie")
        verbose_name_plural = _("movies")
        ordering = ("-release_date", "title")

    def __str__(self) -> str:
        return self.title
