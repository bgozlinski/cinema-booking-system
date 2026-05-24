from rest_framework.routers import SimpleRouter

from apps.cinema.api.viewsets import (
    ActorViewSet,
    DirectorViewSet,
    GenreViewSet,
    HallViewSet,
)

router = SimpleRouter()
router.register("genres", GenreViewSet)
router.register("halls", HallViewSet)
router.register("actors", ActorViewSet)
router.register("directors", DirectorViewSet)

urlpatterns = router.urls
