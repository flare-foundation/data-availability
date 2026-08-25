"""Fetching from an origin, which is a security boundary rather than a detail.

**Every fetch target in this system is attacker-controlled.** A TEE machine's
URL is written to chain by its owner, and a proposer's endpoint will be too. So
a node that resolves and fetches naively is a server-side request forgery engine
pointed at whatever an origin's owner chooses -- cloud metadata endpoints,
internal admin interfaces, anything reachable from the deployment.

Ported from the explorer backend's TEE poller, which deliberately mirrors
go-verifier-api's ``ResolveExternalURL``. Three copies of one blocklist already
exist across two languages; this is the fourth, and consolidating them is
recorded as a cross-repo ask rather than solved here.

The controls, and why each one:

* scheme allowlist, no userinfo -- ``file://`` and credentials-in-URL are not
  transport, they are a way to make the fetcher do something else
* DNS resolved once and the **address pinned** -- otherwise a name that answers
  publicly on the first lookup can answer privately on the second, between the
  check and the connection
* blocklist applied to the resolved address, not the name
* redirects disabled -- a redirect is a second URL that never passed any check
* retries disabled at the transport -- retrying is the scheduler's decision,
  made against a give-up budget it owns
* the size cap bounds what is **read**, not what is kept
"""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

import urllib3

__all__ = ["MAX_RESPONSE_BYTES", "FetchError", "UnsafeURL", "fetch", "resolve"]

MAX_RESPONSE_BYTES: Final = 1 << 20
REQUEST_TIMEOUT_SECONDS: Final = 5.0
DNS_TIMEOUT_SECONDS: Final = 0.75

# Beyond what `ipaddress` already classifies as private, loopback or link-local.
# Mirrors go-verifier-api's blockedIPPrefixes.
_BLOCKED: Final = [
    ipaddress.ip_network("0.0.0.0/8"),  # "this network" (RFC 791)
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT (RFC 6598)
    ipaddress.ip_network("198.18.0.0/15"),  # benchmarking (RFC 2544)
    ipaddress.ip_network("2001:db8::/32"),  # documentation (RFC 3849)
    ipaddress.ip_network("100::/64"),  # discard prefix (RFC 6666)
    ipaddress.ip_network("2002::/16"),  # 6to4 (RFC 3056), embeds private IPv4
    ipaddress.ip_network("2001::/32"),  # Teredo (RFC 4380)
    ipaddress.ip_network("64:ff9b::/96"),  # NAT64 well-known (RFC 6052)
    ipaddress.ip_network("fd00:ec2::254/128"),  # AWS EC2 IPv6 metadata
]

# Bounded on purpose: getaddrinfo has no timeout of its own, so the only way to
# bound it is to run it elsewhere and stop waiting. A saturated pool reports as
# a DNS timeout, which is the truthful answer -- we did not resolve in time.
_DNS_POOL: Final = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dal-dns")


class UnsafeURL(Exception):
    """The URL is not one this service may fetch from. Never retryable."""


class FetchError(Exception):
    """The fetch did not complete. Retryable, subject to a give-up budget."""


@dataclass(frozen=True, slots=True)
class Resolved:
    """A URL that passed every check, with the address it must connect to."""

    scheme: str
    host: str  # host[:port] as written -- the Host header
    hostname: str  # bare name -- TLS SNI
    port: int | None
    ip: str


def _dangerous(addr) -> bool:
    if addr.is_link_local or addr.is_multicast or addr.is_unspecified:
        return True
    return any(addr in net for net in _BLOCKED)


def _blocked(addr, allow_private: bool) -> bool:
    if _dangerous(addr):
        # Dangerous addresses stay blocked even for a local deployment: nothing
        # legitimate lives on a multicast or metadata address.
        return True
    if allow_private:
        return False
    return addr.is_loopback or addr.is_private


def resolve(url: str, *, allow_private: bool = False) -> Resolved:
    """Validate a URL and pin the address it resolves to.

    ``allow_private`` exists for deployments where origins genuinely are on the
    local network -- the end-to-end harness runs every machine on loopback. It
    is not a way to skip the checks: the dangerous prefixes stay blocked either
    way.
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise UnsafeURL(f"invalid URL {url!r}: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise UnsafeURL(
            f"unsupported scheme {parsed.scheme!r}: only http and https are allowed"
        )
    if not parsed.netloc:
        raise UnsafeURL("URL host is required")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeURL("URL userinfo is not allowed")

    try:
        hostname, port = parsed.hostname, parsed.port
    except ValueError as exc:  # an unparseable port
        raise UnsafeURL(f"invalid port in {url!r}: {exc}") from exc
    if not hostname:
        raise UnsafeURL("URL hostname is required")

    # A trailing dot is the same name to DNS and a different string to every
    # allowlist written against strings.
    canonical = hostname.rstrip(".").lower()
    if not canonical:
        raise UnsafeURL("URL hostname is required")
    if canonical == "localhost" or canonical.endswith(".localhost"):
        if not allow_private:
            raise UnsafeURL(f"local hostnames are not allowed: {canonical}")

    try:
        literal = ipaddress.ip_address(canonical)
    except ValueError:
        literal = None

    if literal is not None:
        if _blocked(literal, allow_private):
            raise UnsafeURL(f"address is not allowed: {literal}")
        return Resolved(parsed.scheme, parsed.netloc, hostname, port, str(literal))

    future = _DNS_POOL.submit(socket.getaddrinfo, canonical, None)
    try:
        addresses = future.result(timeout=DNS_TIMEOUT_SECONDS)
    except FutureTimeoutError as exc:
        future.cancel()
        raise UnsafeURL(f"DNS lookup for {canonical!r} timed out") from exc
    except socket.gaierror as exc:
        raise UnsafeURL(f"DNS lookup for {canonical!r} failed: {exc}") from exc

    if not addresses:
        raise UnsafeURL(f"DNS lookup for {canonical!r} returned nothing")

    # The FIRST address is pinned and checked. Checking one and connecting to
    # another is the whole bug this function exists to prevent.
    addr = ipaddress.ip_address(addresses[0][4][0])
    if _blocked(addr, allow_private):
        raise UnsafeURL(f"{canonical} resolves to a disallowed address: {addr}")

    return Resolved(parsed.scheme, parsed.netloc, hostname, port, str(addr))


def fetch(
    resolved: Resolved,
    path_and_query: str,
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    max_bytes: int = MAX_RESPONSE_BYTES,
) -> tuple[int, bytes]:
    """GET from the pinned address, returning ``(status, body)``.

    The connection goes to the pinned IP while the ``Host`` header and TLS SNI
    carry the original name, so virtual hosting and certificate validation both
    still work against the name the origin registered.
    """
    port = resolved.port or (443 if resolved.scheme == "https" else 80)

    if resolved.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            resolved.ip,
            port=port,
            timeout=urllib3.Timeout(connect=timeout, read=timeout),
            server_hostname=resolved.hostname,
            assert_hostname=resolved.hostname,
            cert_reqs="CERT_REQUIRED",
            maxsize=1,
        )
    else:
        pool = urllib3.HTTPConnectionPool(
            resolved.ip,
            port=port,
            timeout=urllib3.Timeout(connect=timeout, read=timeout),
            maxsize=1,
        )

    try:
        response = pool.request(
            "GET",
            path_and_query,
            headers={"Host": resolved.host, "Accept": "application/json"},
            redirect=False,
            retries=False,
            preload_content=False,
        )
    except urllib3.exceptions.HTTPError as exc:
        pool.close()
        raise FetchError(f"fetching {resolved.host}{path_and_query}: {exc}") from exc

    try:
        body = response.read(max_bytes)
        # Read one more byte rather than trusting Content-Length: the cap has to
        # bound what crosses the socket, not what the origin claims it sent.
        if response.read(1):
            raise FetchError(
                f"response from {resolved.host} exceeded {max_bytes} bytes"
            )
        return response.status, body
    finally:
        response.release_conn()
        pool.close()
