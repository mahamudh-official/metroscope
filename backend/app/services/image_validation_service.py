"""Image MIME, header, and network safety validation service.

Enforces robust pre-publication verification for article hero images:
1. Supported MIME types: image/jpeg, image/png, image/webp.
2. Rejection of text/html, application/json, text/plain, missing Content-Type, and unsupported formats.
3. Server-Side Request Forgery (SSRF) mitigation: blocks loopback, private RFC1918, link-local,
   multicast, reserved IP addresses, and non-HTTP(S) schemes.
4. Bounded execution: strict connect/read timeouts (max 4.0s) and bounded streaming (max 512 bytes read).
5. Safe redirect tracking with validation of final destination host and IP.
6. Separation of concerns: MIME validity never grants copyright permission.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any, Optional, Set, Tuple
from urllib.parse import urlparse

import httpcore
from httpcore._backends.auto import AutoBackend
from httpcore._backends.sync import SyncBackend
import httpx
from app.core.logging import logger

SUPPORTED_IMAGE_MIMES: Set[str] = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}

# Maximum allowed Content-Length for an image (20 MB)
MAX_IMAGE_BYTES = 20 * 1024 * 1024

# Default timeouts for image probe
PROBE_TIMEOUT = httpx.Timeout(connect=3.0, read=4.0, write=3.0, pool=3.0)


class ImageValidationError(Exception):
    """Raised when image validation fails."""
    pass


def is_safe_ip(ip_str: str) -> bool:
    """Checks whether an IP address is safe for outbound external requests (SSRF defense)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_loopback:  # 127.0.0.0/8, ::1
            return False
        if ip.is_private:   # 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7
            return False
        if ip.is_link_local:  # 169.254.0.0/16, fe80::/10
            return False
        if ip.is_multicast:
            return False
        if ip.is_reserved:
            return False
        if ip.is_unspecified:  # 0.0.0.0, ::
            return False
        return True
    except ValueError:
        return False


def is_safe_host(hostname: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validates that a hostname does not resolve to private, loopback, or reserved IP space."""
    if not hostname:
        return False, "Missing hostname in image URL"

    clean_host = hostname.strip().lower()

    # Reject localhost and local development names
    if clean_host in {"localhost", "localhost.localdomain", "broadcasthost"} or clean_host.endswith(".local") or clean_host.endswith(".internal"):
        return False, f"Prohibited local/private hostname '{clean_host}'"

    # Reject cloud metadata services directly
    if clean_host in {"169.254.169.254", "metadata.google.internal", "instance-data"}:
        return False, "Prohibited cloud metadata hostname"

    # Direct IP literal check
    try:
        ip = ipaddress.ip_address(clean_host)
        if not is_safe_ip(str(ip)):
            return False, f"Prohibited private/loopback IP address '{clean_host}'"
        return True, None
    except ValueError:
        pass  # It's a domain name, proceed to DNS resolution check

    # DNS resolution check
    try:
        addr_info = socket.getaddrinfo(clean_host, None)
        if not addr_info:
            return False, f"Failed to resolve hostname '{clean_host}'"
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if not is_safe_ip(ip_str):
                return False, f"Hostname '{clean_host}' resolves to prohibited private/internal IP '{ip_str}'"
    except socket.gaierror as err:
        return False, f"DNS resolution failed for '{clean_host}': {err}"
    except Exception as exc:
        return False, f"Host validation error for '{clean_host}': {exc}"

    return True, None


def verify_image_magic_bytes(header_bytes: bytes, mime_type: str) -> bool:
    """Validates that the initial payload bytes match the declared MIME type signature."""
    if not header_bytes:
        return False
    clean_mime = mime_type.lower()

    if clean_mime in {"image/jpeg", "image/jpg"}:
        return header_bytes.startswith(b"\xff\xd8\xff")
    elif clean_mime == "image/png":
        return header_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    elif clean_mime == "image/webp":
        return len(header_bytes) >= 12 and header_bytes.startswith(b"RIFF") and header_bytes[8:12] == b"WEBP"
    return False


class SSRFSafeAsyncBackend(AutoBackend):
    """Network backend that enforces SSRF checks at the TCP socket layer, eliminating TOCTOU DNS rebinding."""

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Any = None,
    ) -> Any:
        if port not in {443, 80}:
            raise ImageValidationError(f"Prohibited non-standard port {port} in image connection")
        safe, err = is_safe_host(host)
        if not safe:
            raise ImageValidationError(f"SSRF Protection: {err}")
        addr_info = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        if not addr_info:
            raise ImageValidationError(f"Failed to resolve host '{host}'")
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if not is_safe_ip(ip_str):
                raise ImageValidationError(f"SSRF Protection: Host '{host}' resolved to unsafe IP '{ip_str}'")
        target_ip = addr_info[0][4][0]
        return await super().connect_tcp(
            target_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class SSRFSafeSyncBackend(SyncBackend):
    """Synchronous network backend enforcing SSRF checks at the TCP socket layer."""

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Any = None,
    ) -> Any:
        if port not in {443, 80}:
            raise ImageValidationError(f"Prohibited non-standard port {port} in image connection")
        safe, err = is_safe_host(host)
        if not safe:
            raise ImageValidationError(f"SSRF Protection: {err}")
        addr_info = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        if not addr_info:
            raise ImageValidationError(f"Failed to resolve host '{host}'")
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if not is_safe_ip(ip_str):
                raise ImageValidationError(f"SSRF Protection: Host '{host}' resolved to unsafe IP '{ip_str}'")
        target_ip = addr_info[0][4][0]
        return super().connect_tcp(
            target_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


def create_ssrf_safe_async_client() -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport()
    transport._pool = httpcore.AsyncConnectionPool(network_backend=SSRFSafeAsyncBackend())
    return httpx.AsyncClient(
        transport=transport,
        timeout=PROBE_TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": "MetroScope-ImageValidator/1.0 (+https://themetroscope.com)"},
    )


def create_ssrf_safe_sync_client() -> httpx.Client:
    transport = httpx.HTTPTransport()
    transport._pool = httpcore.ConnectionPool(network_backend=SSRFSafeSyncBackend())
    return httpx.Client(
        transport=transport,
        timeout=PROBE_TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": "MetroScope-ImageValidator/1.0 (+https://themetroscope.com)"},
    )


class ImageValidationService:
    """Service providing synchronous and asynchronous image MIME and network safety checks."""

    @classmethod
    def validate_url_syntax(cls, image_url: Optional[str]) -> Tuple[bool, Optional[str]]:
        if not image_url or not isinstance(image_url, str):
            return False, "Image URL is missing or empty"
        cleaned = image_url.strip()
        if len(cleaned) < 10:
            return False, f"Image URL too short ({len(cleaned)} chars)"
        if not cleaned.startswith("https://"):
            return False, f"Image URL must use secure HTTPS protocol: '{cleaned}'"

        lower = cleaned.lower()
        if any(bad in lower for bad in ["pixel.gif", "1x1", "tracking", "placeholder", "default_image", "blank.png"]):
            return False, f"Placeholder or tracking pixel image rejected: '{cleaned}'"

        parsed = urlparse(cleaned)
        if not parsed.netloc:
            return False, "Invalid image URL structure: missing network location"
        if parsed.port and parsed.port not in {443, 80}:
            return False, f"Prohibited non-standard port {parsed.port} in image URL"

        return True, None

    @classmethod
    async def validate_image_response_async(
        cls,
        image_url: str,
        client: Optional[httpx.AsyncClient] = None,
        max_redirects: int = 3,
    ) -> Tuple[bool, Optional[str]]:
        """Performs async network probe validating SSRF safety, HTTP status, Content-Type, and magic bytes."""
        syntax_ok, syntax_err = cls.validate_url_syntax(image_url)
        if not syntax_ok:
            return False, syntax_err

        current_url = image_url
        redirect_count = 0

        owns_client = client is None
        async_client = client or create_ssrf_safe_async_client()

        try:
            while redirect_count <= max_redirects:
                parsed = urlparse(current_url)
                if parsed.scheme.lower() != "https":
                    return False, f"Image redirect to insecure non-HTTPS destination: '{current_url}'"

                safe_host, host_err = is_safe_host(parsed.hostname)
                if not safe_host:
                    return False, f"SSRF Protection: {host_err}"

                # Try HEAD first
                try:
                    head_resp = await async_client.head(current_url)
                    status = head_resp.status_code

                    # Handle Redirect
                    if status in {301, 302, 303, 307, 308}:
                        redirect_url = head_resp.headers.get("Location")
                        if not redirect_url:
                            return False, f"HTTP {status} redirect missing Location header"
                        # Resolve relative redirect
                        if redirect_url.startswith("/"):
                            current_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                        else:
                            current_url = redirect_url
                        redirect_count += 1
                        continue

                    # If HEAD succeeded (200), inspect Content-Type and Content-Length
                    if status == 200:
                        content_type_raw = head_resp.headers.get("Content-Type", "")
                        clean_mime = content_type_raw.split(";")[0].strip().lower()

                        if not clean_mime:
                            return False, "Image response missing Content-Type header"

                        if clean_mime not in SUPPORTED_IMAGE_MIMES:
                            return False, f"Unsupported image MIME type: '{clean_mime}'. Expected image/jpeg, image/png, or image/webp"

                        content_len_str = head_resp.headers.get("Content-Length")
                        if content_len_str:
                            try:
                                if int(content_len_str) > MAX_IMAGE_BYTES:
                                    return False, f"Image size ({content_len_str} bytes) exceeds limit of {MAX_IMAGE_BYTES} bytes"
                            except ValueError:
                                pass

                        # Verified via HEAD
                        return True, None

                    elif status in {400, 401, 403, 404, 410, 500, 502, 503}:
                        return False, f"Image URL returned HTTP {status}"

                except (httpx.TimeoutException, TimeoutError):
                    return False, "Image HEAD request timed out"
                except Exception:
                    # Some servers reject HEAD; fall through to streaming GET
                    pass

                # Streaming GET with bounded read
                try:
                    async with async_client.stream("GET", current_url) as stream_resp:
                        status = stream_resp.status_code

                        # Handle redirect in GET
                        if status in {301, 302, 303, 307, 308}:
                            redirect_url = stream_resp.headers.get("Location")
                            if not redirect_url:
                                return False, f"HTTP {status} redirect missing Location header"
                            if redirect_url.startswith("/"):
                                current_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                            else:
                                current_url = redirect_url
                            redirect_count += 1
                            continue

                        if status != 200:
                            return False, f"Image URL returned HTTP {status}"

                        content_type_raw = stream_resp.headers.get("Content-Type", "")
                        clean_mime = content_type_raw.split(";")[0].strip().lower()

                        if not clean_mime:
                            return False, "Image response missing Content-Type header"

                        if clean_mime not in SUPPORTED_IMAGE_MIMES:
                            return False, f"Unsupported image MIME type: '{clean_mime}'. Expected image/jpeg, image/png, or image/webp"

                        content_len_str = stream_resp.headers.get("Content-Length")
                        if content_len_str:
                            try:
                                if int(content_len_str) > MAX_IMAGE_BYTES:
                                    return False, f"Image size ({content_len_str} bytes) exceeds limit of {MAX_IMAGE_BYTES} bytes"
                            except ValueError:
                                pass

                        # Read at most 512 bytes for signature verification
                        chunk = b""
                        async for part in stream_resp.aiter_bytes(chunk_size=512):
                            chunk += part
                            if len(chunk) >= 512:
                                break

                        if not chunk:
                            return False, "Image response body is empty"

                        # Signature verification
                        if not verify_image_magic_bytes(chunk[:32], clean_mime):
                            return False, f"Image payload does not match declared MIME signature '{clean_mime}'"

                        return True, None

                except (httpx.TimeoutException, TimeoutError):
                    return False, "Image request timed out"
                except httpx.RequestError as req_err:
                    return False, f"Image request failed: {req_err}"

            return False, f"Too many redirects ({redirect_count}) while resolving image URL"

        finally:
            if owns_client:
                await async_client.aclose()

    @classmethod
    def validate_image_response_sync(
        cls,
        image_url: str,
        client: Optional[httpx.Client] = None,
        max_redirects: int = 3,
    ) -> Tuple[bool, Optional[str]]:
        """Synchronous version of validate_image_response for pre-flight and unit validation."""
        syntax_ok, syntax_err = cls.validate_url_syntax(image_url)
        if not syntax_ok:
            return False, syntax_err

        current_url = image_url
        redirect_count = 0

        owns_client = client is None
        sync_client = client or create_ssrf_safe_sync_client()

        try:
            while redirect_count <= max_redirects:
                parsed = urlparse(current_url)
                if parsed.scheme.lower() != "https":
                    return False, f"Image redirect to insecure non-HTTPS destination: '{current_url}'"

                safe_host, host_err = is_safe_host(parsed.hostname)
                if not safe_host:
                    return False, f"SSRF Protection: {host_err}"

                # Try HEAD first
                try:
                    head_resp = sync_client.head(current_url)
                    status = head_resp.status_code

                    if status in {301, 302, 303, 307, 308}:
                        redirect_url = head_resp.headers.get("Location")
                        if not redirect_url:
                            return False, f"HTTP {status} redirect missing Location header"
                        if redirect_url.startswith("/"):
                            current_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                        else:
                            current_url = redirect_url
                        redirect_count += 1
                        continue

                    if status == 200:
                        content_type_raw = head_resp.headers.get("Content-Type", "")
                        clean_mime = content_type_raw.split(";")[0].strip().lower()

                        if not clean_mime:
                            return False, "Image response missing Content-Type header"

                        if clean_mime not in SUPPORTED_IMAGE_MIMES:
                            return False, f"Unsupported image MIME type: '{clean_mime}'. Expected image/jpeg, image/png, or image/webp"

                        content_len_str = head_resp.headers.get("Content-Length")
                        if content_len_str:
                            try:
                                if int(content_len_str) > MAX_IMAGE_BYTES:
                                    return False, f"Image size exceeds limit of {MAX_IMAGE_BYTES} bytes"
                            except ValueError:
                                pass

                        return True, None

                    elif status in {400, 401, 403, 404, 410, 500, 502, 503}:
                        return False, f"Image URL returned HTTP {status}"

                except (httpx.TimeoutException, TimeoutError):
                    return False, "Image HEAD request timed out"
                except Exception:
                    pass

                # Streaming GET with bounded read
                try:
                    with sync_client.stream("GET", current_url) as stream_resp:
                        status = stream_resp.status_code

                        if status in {301, 302, 303, 307, 308}:
                            redirect_url = stream_resp.headers.get("Location")
                            if not redirect_url:
                                return False, f"HTTP {status} redirect missing Location header"
                            if redirect_url.startswith("/"):
                                current_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                            else:
                                current_url = redirect_url
                            redirect_count += 1
                            continue

                        if status != 200:
                            return False, f"Image URL returned HTTP {status}"

                        content_type_raw = stream_resp.headers.get("Content-Type", "")
                        clean_mime = content_type_raw.split(";")[0].strip().lower()

                        if not clean_mime:
                            return False, "Image response missing Content-Type header"

                        if clean_mime not in SUPPORTED_IMAGE_MIMES:
                            return False, f"Unsupported image MIME type: '{clean_mime}'. Expected image/jpeg, image/png, or image/webp"

                        content_len_str = stream_resp.headers.get("Content-Length")
                        if content_len_str:
                            try:
                                if int(content_len_str) > MAX_IMAGE_BYTES:
                                    return False, f"Image size exceeds limit of {MAX_IMAGE_BYTES} bytes"
                            except ValueError:
                                pass

                        chunk = b""
                        for part in stream_resp.iter_bytes(chunk_size=512):
                            chunk += part
                            if len(chunk) >= 512:
                                break

                        if not chunk:
                            return False, "Image response body is empty"

                        if not verify_image_magic_bytes(chunk[:32], clean_mime):
                            return False, f"Image payload does not match declared MIME signature '{clean_mime}'"

                        return True, None

                except (httpx.TimeoutException, TimeoutError):
                    return False, "Image request timed out"
                except httpx.RequestError as req_err:
                    return False, f"Image request failed: {req_err}"

            return False, f"Too many redirects ({redirect_count}) while resolving image URL"

        finally:
            if owns_client:
                sync_client.close()
