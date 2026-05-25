from django import forms
from django.utils.translation import gettext_lazy as _

from apps.cinema.models import Genre


class MovieFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": _("Tytuł filmu..."), "class": "form-control"}),
        label="",
    )
    genre = forms.ModelChoiceField(
        queryset=Genre.objects.all(),
        required=False,
        empty_label=_("Wszystkie gatunki"),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="",
    )
