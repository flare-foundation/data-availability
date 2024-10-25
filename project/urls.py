"""DjangoTemplateProject URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.urls import include, path
from drf_spectacular.utils import extend_schema, inline_serializer
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import decorators, response, serializers, status


@extend_schema(
    responses=inline_serializer(
        name="Health",
        fields={"healthy": serializers.BooleanField()},
    )
)
@decorators.api_view(["get"])
def health(request):
    return response.Response({"healthy": True}, status=status.HTTP_200_OK)


urlpatterns = [
    # drf-spectacular schema and ui endpoints
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("api/health", health),
]

# v0 api
urlpatterns += [
    path("api/v0/", include("ftso.urls")),
    path("api/v0/", include("fsp.urls")),
    path("api/v0/", include("fdc.urls")),
]

if "django_prometheus" in settings.INSTALLED_APPS:
    urlpatterns.append(path("", include("django_prometheus.urls")))
