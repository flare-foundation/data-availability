"""Serving what the store holds.

**Bytes, verbatim, under a 32-byte key.** That is the whole contract between
nodes, and it is deliberately not a REST resource: no envelope, no content
negotiation, no field selection. A caller binds what it receives to a hash it
already has, so anything this layer added would have to be stripped before the
binding could be checked.

The path shape matters more than it looks. Every existing consumer builds its URL
as ``base + "/" + hex`` -- the FDC2 verifier, the relay client and the
facilitator all do -- so a node is a drop-in for the file server they read today
when its base URL points here.

Two lookups, one route:

* a **primary** key returns one artifact or nothing, which is what a caller
  holding a `packageHash` or an action-result key asks
* a **secondary** key returns the set it names, because a node that missed a
  trigger asks "what do you hold for this instruction" -- a question no unique
  key can express (§5.5)
"""

from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_safe

from dal.models import Artifact, ArtifactIndex

__all__ = ["artifact", "health"]

# Serving raw bytes rather than a JSON envelope, so the content type says so.
OCTET_STREAM = "application/octet-stream"


def _normalise(key: str) -> str:
    """Lowercase, unprefixed hex. A key is 32 bytes and nothing else is one."""
    key = key.removeprefix("0x").removeprefix("0X").lower()
    if len(key) != 64:
        raise Http404("a key is 32 bytes of hex")
    try:
        bytes.fromhex(key)
    except ValueError as exc:
        raise Http404("a key is 32 bytes of hex") from exc
    return key


@require_safe
def artifact(request, key: str):
    """``GET``/``HEAD /artifact/<key>`` — the admitted bytes, exactly as fetched.

    A HEAD answers existence and size without moving the body, which is what a
    peer deciding whether to sync needs and what a monitor should use.
    """
    key = _normalise(key)

    try:
        found = Artifact.objects.get(key=key)
    except Artifact.DoesNotExist:
        return _by_index(request, key)

    if request.method == "HEAD":
        response = HttpResponse(content_type=OCTET_STREAM)
        response["Content-Length"] = str(found.size_bytes)
    else:
        # bytes(): psycopg hands back a memoryview, and a memoryview reaches the
        # wire as its repr rather than as its contents.
        response = HttpResponse(bytes(found.raw), content_type=OCTET_STREAM)

    response["X-DAL-Message-Class"] = found.message_class
    return response


def _by_index(request, key: str):
    """A secondary key names a SET, so it answers in JSON rather than in bytes.

    Except when it names exactly one, which is the common case — a txid naming
    the single proposal that describes it — and where answering with the bytes
    keeps the caller from needing to know which kind of key it held.
    """
    entries = list(
        ArtifactIndex.objects.filter(index_key=key).select_related("artifact")
    )
    if not entries:
        raise Http404("no artifact under that key")

    if len(entries) == 1:
        found = entries[0].artifact
        if request.method == "HEAD":
            response = HttpResponse(content_type=OCTET_STREAM)
            response["Content-Length"] = str(found.size_bytes)
        else:
            response = HttpResponse(bytes(found.raw), content_type=OCTET_STREAM)
        response["X-DAL-Message-Class"] = found.message_class
        return response

    return JsonResponse(
        {
            "index": key,
            "artifacts": [
                {
                    "key": e.artifact.key,
                    "messageClass": e.artifact.message_class,
                    "sizeBytes": e.artifact.size_bytes,
                }
                for e in entries
            ],
        }
    )


@require_safe
def health(request):
    """What this node holds, for a peer ranking who is worth asking (§7.3)."""
    return JsonResponse(
        {
            "healthy": True,
            "artifacts": Artifact.objects.count(),
            "byClass": {
                row["message_class"]: row["n"]
                for row in Artifact.objects.values("message_class")
                .annotate(n=Count("id"))
                .order_by()
            },
        }
    )
