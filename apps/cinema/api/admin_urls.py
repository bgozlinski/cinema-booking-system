from rest_framework.routers import SimpleRouter

from apps.cinema.api.admin import (
    AdminActorViewSet,
    AdminDirectorViewSet,
    AdminGenreViewSet,
    AdminHallViewSet,
    AdminMovieViewSet,
    AdminScreeningViewSet,
)

router = SimpleRouter()
router.register("movies", AdminMovieViewSet)
router.register("screenings", AdminScreeningViewSet)
router.register("genres", AdminGenreViewSet)
router.register("halls", AdminHallViewSet)
router.register("actors", AdminActorViewSet)
router.register("directors", AdminDirectorViewSet)

urlpatterns = router.urls
