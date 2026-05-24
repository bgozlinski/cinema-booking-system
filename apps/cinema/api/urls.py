from rest_framework.routers import SimpleRouter

from apps.cinema.api.viewsets import (
    ActorViewSet,
    DirectorViewSet,
    GenreViewSet,
    HallViewSet,
    MovieViewSet,
)

router = SimpleRouter()
router.register("movies", MovieViewSet)
router.register("genres", GenreViewSet)
router.register("halls", HallViewSet)
router.register("actors", ActorViewSet)
router.register("directors", DirectorViewSet)

urlpatterns = router.urls
