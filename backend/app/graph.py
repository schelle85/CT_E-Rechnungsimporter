"""Small, mailbox-bound Graph v1.0 adapter. No worker or public HTTP routes."""
from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
import stat
import time
from urllib.parse import quote, unquote, urlsplit
from uuid import UUID

import httpx

ORIGIN = "https://graph.microsoft.com"
SCOPE = ORIGIN + "/.default"
JSON_LIMIT = 2 * 1024 * 1024


class GraphError(Exception):
    """Only neutral codes cross the adapter boundary, never upstream text/URLs."""
    def __init__(self, code, status=None, uncertain=False):
        self.code, self.status, self.uncertain = code, status, uncertain
        super().__init__(code)


def protected_bytes(path):
    """Operator files: root-owned regular file, no links/world access/writers."""
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_mode & 0o027 or info.st_size > 65536):
            raise ValueError()
        with os.fdopen(fd, "rb") as source:
            fd = None
            value = source.read(65537)
        if len(value) > 65536:
            raise ValueError()
        return value
    except (OSError, ValueError):
        raise GraphError("graph_operator_file_unavailable") from None
    finally:
        if fd is not None:
            os.close(fd)


@dataclass(frozen=True, repr=False)
class GraphConfig:
    tenant_id: str
    client_id: str
    mailbox: str

    def __post_init__(self):
        try:
            UUID(self.tenant_id)
            UUID(self.client_id)
            local, domain = self.mailbox.split("@")
            if (not local or not domain or "." not in domain or len(self.mailbox) > 254
                    or any(c.isspace() or ord(c) < 33 or c in "/\\?#%" for c in self.mailbox)):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise GraphError("graph_configuration_invalid") from None

    @classmethod
    def load(cls, path):
        try:
            value = json.loads(protected_bytes(path))
            if set(value) != {"tenant_id", "client_id", "mailbox"}:
                raise ValueError()
            return cls(**value)
        except (ValueError, TypeError):
            raise GraphError("graph_configuration_invalid") from None


class GraphClient:
    def __init__(self, config, credential, http, *, sleep=time.sleep, clock=time.monotonic):
        self.config, self.credential, self.http = config, credential, http
        self.sleep, self.clock = sleep, clock
        self.root = ORIGIN + "/v1.0/users/" + quote(config.mailbox, safe="")

    def _checked_url(self, url, collection=None):
        try:
            part = urlsplit(url)
            root = urlsplit(self.root)
            if (part.scheme != "https" or part.netloc.lower() != "graph.microsoft.com"
                    or part.fragment or not unquote(part.path).startswith(unquote(root.path) + "/")
                    or any(s in (".", "..") for s in unquote(part.path).split("/"))):
                raise ValueError()
            if collection is not None and unquote(part.path) != unquote(urlsplit(collection).path):
                raise ValueError()
            return url
        except (ValueError, AttributeError, TypeError):
            raise GraphError("graph_untrusted_url") from None

    def _headers(self):
        try:
            token = self.credential.get_token(SCOPE).token
            if not isinstance(token, str) or not token or "\r" in token or "\n" in token:
                raise ValueError()
            return {"Authorization": "Bearer " + token, "Prefer": 'IdType="ImmutableId"',
                    "Accept": "application/json", "Accept-Encoding": "identity"}
        except Exception:
            raise GraphError("graph_authentication_failed") from None

    @contextmanager
    def _response(self, method, url, *, params=None, payload=None):
        self._checked_url(url)
        # Retry only reads, with a small bounded budget. No implicit write replay.
        for attempt in range(3 if method == "GET" else 1):
            try:
                with self.http.stream(method, url, params=params, json=payload,
                                      headers=self._headers(), follow_redirects=False) as response:
                    if method == "GET" and response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        value = response.headers.get("Retry-After", "1")
                        try:
                            delay = int(value)
                        except ValueError:
                            delay = 1
                        if not 0 <= delay <= 5:
                            raise GraphError("graph_retry_later", response.status_code)
                        response.close()
                        self.sleep(delay)
                        continue
                    if not 200 <= response.status_code < 300:
                        status = response.status_code
                        code = {401: "graph_unauthorized", 403: "graph_forbidden", 404: "graph_not_found",
                                429: "graph_retry_later"}.get(status, "graph_http_error")
                        raise GraphError(code, status, method != "GET" and status >= 500)
                    if response.headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
                        raise GraphError("graph_unexpected_encoding", uncertain=method != "GET")
                    yield response
                    return
            except (httpx.HTTPError, OSError):
                raise GraphError("graph_transport_error", uncertain=method != "GET") from None

    def _json(self, method, url, *, params=None, payload=None):
        from app.graph_deadline import request_deadline
        data = bytearray()
        started = self.clock()
        with request_deadline(45, uncertain=method != "GET"):
            with self._response(method, url, params=params, payload=payload) as response:
                # No ByteChunker buffering: inspect every transport piece immediately.
                for chunk in response.iter_bytes():
                    if len(data) + len(chunk) > JSON_LIMIT or self.clock() - started >= 45:
                        raise GraphError("graph_response_limit", uncertain=method != "GET")
                    data.extend(chunk)
        try:
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except (ValueError, UnicodeError):
            raise GraphError("graph_invalid_response", uncertain=method != "GET") from None

    def probe(self):
        value = self._json("GET", self.root + "/mailFolders/inbox", params={"$select": "id"})
        if not isinstance(value.get("id"), str) or not value["id"]:
            raise GraphError("graph_invalid_response")
        return {"mailbox_access": "ok"}


@contextmanager
def operator_client(config_path, certificate_path):
    from azure.identity import CertificateCredential
    config = GraphConfig.load(config_path)
    pem = protected_bytes(certificate_path)
    credential = None
    try:
        credential = CertificateCredential(config.tenant_id, config.client_id, certificate_data=pem,
            retry_total=0, connection_timeout=10, read_timeout=20)
        with httpx.Client(timeout=httpx.Timeout(20, connect=5), trust_env=False,
                          follow_redirects=False, limits=httpx.Limits(max_connections=2)) as http:
            yield GraphClient(config, credential, http)
    except GraphError:
        raise
    except Exception:
        raise GraphError("graph_runtime_unavailable") from None
    finally:
        if credential is not None:
            try:
                credential.close()
            except Exception:
                raise GraphError("graph_runtime_unavailable") from None
