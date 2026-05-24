from rest_framework import serializers

from apps.cinema.models import Actor, Director, Genre, Hall


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name")


class HallSerializer(serializers.ModelSerializer):
    class Meta:
        model = Hall
        fields = ("id", "name", "description", "capacity")


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = ("id", "full_name", "photo", "biography")


class DirectorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Director
        fields = ("id", "full_name", "photo", "biography")
