from rest_framework.routers import SimpleRouter

from ..views.v1 import AttestationResultV1ViewSet

router = SimpleRouter(trailing_slash=False)

router.register("fdc", AttestationResultV1ViewSet, basename="attestationresult")

urlpatterns = [*router.urls]
