"""Routes for the byte-serving API.

No trailing slashes: every existing consumer builds ``base + "/" + hex`` and
Django's ``APPEND_SLASH`` would answer a redirect none of them follow.
"""

from django.urls import path

from dal import views

app_name = "dal"

urlpatterns = [
    path("artifact/<str:key>", views.artifact, name="artifact"),
    path("health", views.health, name="health"),
]
