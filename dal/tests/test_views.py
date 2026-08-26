"""The byte-serving API.

Its contract is narrow on purpose: a 32-byte key in, the admitted bytes out,
nothing added. Every test here is about that narrowness, because the moment this
layer decorates a response the caller can no longer bind what it received to the
hash it already had.
"""

import pytest
from django.utils import timezone

from dal.models import Artifact, ArtifactIndex

# The DAL's routes are loaded ALONE. Loading the project's root URL conf would
# pull in configuration.config, which builds the whole FTSO/FDC configuration at
# import and refuses to start without a live Flare RPC — and the byte API needs
# none of it. That the override works is itself the point: this layer is
# independent of everything else the service does.
pytestmark = pytest.mark.urls("dal.urls")

KEY = "aa" * 32
OTHER = "bb" * 32
INDEX = "cc" * 32
BODY = b'{"result":{"ok":true},"signature":"0x00"}'


def make(key=KEY, raw=BODY, message_class="tee_action_result"):
    return Artifact.objects.create(
        key=key,
        message_class=message_class,
        raw=raw,
        origin="http://93.184.216.34/",
        gated_at=timezone.now(),
        size_bytes=len(raw),
    )


def url(key):
    # Literal, not reverse(): the PATH is the contract here. Every consumer
    # builds `base + "/" + hex`, so a test that went through the router could
    # pass while the wire shape drifted.
    return f"/artifact/{key}"


@pytest.mark.django_db
class TestPrimaryLookup:
    def test_the_bytes_come_back_exactly(self, client):
        make()
        response = client.get(url(KEY))
        assert response.status_code == 200
        assert response.content == BODY
        assert response["Content-Type"] == "application/octet-stream"

    def test_binary_survives_the_round_trip(self, client):
        # bytea comes back as a memoryview, which reaches the wire as its repr
        # rather than its contents unless something converts it. A consumer
        # would see plausible-looking bytes that hash to nothing.
        raw = bytes(range(256))
        make(raw=raw)
        assert client.get(url(KEY)).content == raw

    def test_head_answers_existence_and_size_without_a_body(self, client):
        make()
        response = client.head(url(KEY))
        assert response.status_code == 200
        assert response.content == b""
        assert response["Content-Length"] == str(len(BODY))

    def test_a_missing_key_is_404(self, client):
        assert client.get(url(KEY)).status_code == 404

    def test_the_message_class_is_advertised(self, client):
        # A header rather than a wrapper: a caller that does not care never has
        # to parse past it.
        make()
        assert client.get(url(KEY))["X-DAL-Message-Class"] == "tee_action_result"


@pytest.mark.django_db
class TestKeyShape:
    @pytest.mark.parametrize(
        "bad", ["", "aa", "zz" * 32, "aa" * 31, "aa" * 33], ids=repr
    )
    def test_only_32_bytes_of_hex_is_a_key(self, client, bad):
        assert client.get(f"/artifact/{bad}").status_code == 404

    def test_a_prefixed_or_uppercase_key_still_resolves(self, client):
        # Callers render hashes both ways; one artifact must not need two
        # requests to find.
        make()
        assert client.get(url("0x" + KEY.upper())).status_code == 200


@pytest.mark.django_db
class TestSecondaryLookup:
    def test_an_index_naming_one_artifact_answers_with_its_bytes(self, client):
        # The common case: a txid naming the single proposal that describes it.
        # Answering with bytes means a caller need not know which kind of key it
        # was holding.
        ArtifactIndex.objects.create(index_key=INDEX, artifact=make())
        response = client.get(url(INDEX))
        assert response.status_code == 200
        assert response.content == BODY

    def test_an_index_naming_several_answers_with_the_set(self, client):
        # A secondary lookup is set-valued by design, and collapsing it to one
        # would make which artifact you got depend on insertion order.
        for key in (KEY, OTHER):
            ArtifactIndex.objects.create(index_key=INDEX, artifact=make(key=key))
        response = client.get(url(INDEX))
        assert response.status_code == 200
        body = response.json()
        assert {a["key"] for a in body["artifacts"]} == {KEY, OTHER}

    def test_an_index_entry_whose_artifact_was_evicted_is_gone(self, client):
        # Retention deletes artifacts; a dangling index entry would answer a
        # peer with a promise the node cannot keep.
        found = make()
        ArtifactIndex.objects.create(index_key=INDEX, artifact=found)
        found.delete()
        assert client.get(url(INDEX)).status_code == 404


@pytest.mark.django_db
class TestMethods:
    def test_writes_are_refused(self, client):
        # Pull-only (D5). Nothing enters this store through the read API, and a
        # node that accepted a push would have an unsolicited-data path the gate
        # was never designed to stand in front of.
        make()
        for method in (client.post, client.put, client.delete, client.patch):
            assert method(url(KEY)).status_code == 405


@pytest.mark.django_db
class TestHealth:
    def test_health_counts_what_is_held(self, client):
        make()
        make(key=OTHER, message_class="proposal")
        body = client.get("/health").json()
        assert body["healthy"] is True
        assert body["artifacts"] == 2
        assert body["byClass"] == {"tee_action_result": 1, "proposal": 1}
