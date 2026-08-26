"""A URL conf carrying ONLY the DAL.

The project's root conf imports the FTSO and FDC views, which import
``configuration.config``, which builds the whole protocol configuration at import
time: a live Flare RPC, a recognised chain id, a `Relay` resolved through
`FlareContractRegistry`. The DAL needs none of that — it reads triggers from an
indexer and state from whatever chain it is pointed at — so a deployment that
serves only the DAL should not inherit the requirement.

Use it with ``ROOT_URLCONF=project.urls_dal``. That is what lets a DAL run beside
a test chain, and it is half the answer to whether one service can be both
archival and interactive: they can share a repository without sharing a process.
"""

from django.urls import include, path

from dal import views

urlpatterns = [
    path("api/dal/", include("dal.urls")),
    path("api/health", views.health),
    # Also at the bare root, because every consumer builds `base + "/" + hex`
    # and pointing one at `…/api/dal/artifact` is a configuration step this
    # saves where the node serves nothing else.
    path("artifact/<str:key>", views.artifact),
]
