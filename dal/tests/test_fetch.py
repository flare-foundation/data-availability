"""The fetch boundary.

Every case here is a URL an origin's owner could write to chain. The resolver is
the only thing standing between that and a request made from inside the
deployment, so the negative cases are the point of the file.
"""

import http.server
import threading

import pytest

from dal.fetch import FetchError, UnsafeURL, fetch, resolve


class TestRejectedURLs:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/x",
            "gopher://example.com/",
            "//example.com/x",
            "not a url at all",
        ],
        ids=str,
    )
    def test_only_http_and_https(self, url):
        with pytest.raises(UnsafeURL):
            resolve(url)

    def test_credentials_in_the_url_are_refused(self):
        # A URL carrying credentials is not a transport detail: it is a way to
        # make this service authenticate somewhere on an origin's behalf.
        with pytest.raises(UnsafeURL, match="userinfo"):
            resolve("http://user:pass@93.184.216.34/")

    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://[::1]/",
            "http://10.0.0.1/",
            "http://192.168.1.1/",
            "http://172.16.0.1/",
            "http://localhost/",
            "http://anything.localhost/",
        ],
        ids=str,
    )
    def test_private_and_local_addresses(self, url):
        with pytest.raises(UnsafeURL):
            resolve(url)

    @pytest.mark.parametrize(
        ("url", "why"),
        [
            ("http://169.254.169.254/", "cloud metadata, link-local"),
            ("http://[fd00:ec2::254]/", "AWS IPv6 metadata"),
            ("http://0.0.0.0/", "this network"),
            ("http://100.64.0.1/", "carrier-grade NAT"),
            ("http://198.18.0.1/", "benchmarking"),
            ("http://[2001:db8::1]/", "documentation"),
            ("http://[2002:a00:1::]/", "6to4 wrapping a private v4"),
            ("http://[64:ff9b::a00:1]/", "NAT64 wrapping a private v4"),
            ("http://224.0.0.1/", "multicast"),
        ],
        ids=lambda v: v if " " not in str(v) else str(v),
    )
    def test_the_dangerous_prefixes(self, url, why):
        with pytest.raises(UnsafeURL):
            resolve(url)

    @pytest.mark.parametrize(
        "url",
        ["http://169.254.169.254/", "http://[fd00:ec2::254]/", "http://224.0.0.1/"],
        ids=str,
    )
    def test_dangerous_prefixes_stay_blocked_even_when_private_is_allowed(self, url):
        # allow_private is for a deployment whose origins really are on the
        # local network. Nothing legitimate lives on a metadata or multicast
        # address, so those stay blocked either way.
        with pytest.raises(UnsafeURL):
            resolve(url, allow_private=True)

    def test_a_trailing_dot_does_not_slip_past_the_name_check(self):
        # "localhost." is the same name to DNS and a different string to any
        # check written against strings.
        with pytest.raises(UnsafeURL):
            resolve("http://localhost./")

    def test_a_name_that_does_not_resolve_is_refused(self):
        with pytest.raises(UnsafeURL, match="DNS"):
            resolve("http://this-name-does-not-exist.invalid/")


class TestAcceptedURLs:
    def test_a_public_literal_is_pinned_to_itself(self):
        r = resolve("https://93.184.216.34:8443/")
        assert (r.ip, r.port, r.scheme) == ("93.184.216.34", 8443, "https")

    def test_loopback_is_allowed_when_the_deployment_says_so(self):
        r = resolve("http://127.0.0.1:8090/", allow_private=True)
        assert r.ip == "127.0.0.1"

    def test_the_host_header_keeps_the_name_as_written(self):
        # The connection goes to the pinned address; the Host header and SNI
        # carry the name, or virtual hosting and certificate validation break.
        r = resolve("http://127.0.0.1:8090/", allow_private=True)
        assert r.host == "127.0.0.1:8090"
        assert r.hostname == "127.0.0.1"


class _Handler(http.server.BaseHTTPRequestHandler):
    body = b'{"ok":true}'
    status = 200

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/")
            self.end_headers()
            return
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


@pytest.fixture
def origin():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


class TestFetch:
    def test_a_body_comes_back_whole(self, origin):
        status, body = fetch(resolve(origin, allow_private=True), "/action/result/x")
        assert (status, body) == (200, b'{"ok":true}')

    def test_a_redirect_is_not_followed(self, origin):
        # The Location here points at cloud metadata. Following it would defeat
        # every check resolve() just performed, on a URL that never passed one.
        status, _ = fetch(resolve(origin, allow_private=True), "/redirect")
        assert status == 302

    def test_an_oversized_body_is_refused(self, origin):
        with pytest.raises(FetchError, match="exceeded"):
            fetch(resolve(origin, allow_private=True), "/", max_bytes=4)

    def test_a_dead_port_raises_a_retryable_error(self):
        # FetchError, not UnsafeURL: an origin that is down is retryable, an
        # origin we may not talk to is not, and the collector treats them
        # differently.
        dead = resolve("http://127.0.0.1:1/", allow_private=True)
        with pytest.raises(FetchError):
            fetch(dead, "/", timeout=1.0)
