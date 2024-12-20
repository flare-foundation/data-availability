from rest_framework.routers import SimpleRouter

from ftso.views import FeedResultViewSet

router = SimpleRouter(trailing_slash=False)

router.register("ftso", FeedResultViewSet, basename="ftsofeed")

urlpatterns = [*router.urls]
