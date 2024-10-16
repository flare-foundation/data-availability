from rest_framework.routers import SimpleRouter

from .views import FspViewSet

router = SimpleRouter(trailing_slash=False)

router.register("fsp", FspViewSet, basename="fsp")

urlpatterns = [*router.urls]
