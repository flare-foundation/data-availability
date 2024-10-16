from rest_framework.routers import SimpleRouter

from .views import AttestationResultViewSet

router = SimpleRouter(trailing_slash=False)

router.register("fdc", AttestationResultViewSet, basename="attestationresult")

urlpatterns = [*router.urls]
