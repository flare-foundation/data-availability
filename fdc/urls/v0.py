from rest_framework.routers import SimpleRouter

from ..views.v0 import AttestationResultV0ViewSet

router = SimpleRouter(trailing_slash=False)

router.register("fdc", AttestationResultV0ViewSet, basename="attestationresult")

urlpatterns = [*router.urls]
