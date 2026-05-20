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
