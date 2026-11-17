"""Only the bound application's selected GET/addKey/removeKey. Never replay POST."""
from contextlib import contextmanager
from datetime import datetime, timezone
import base64
import json
import time

import httpx
from app.graph import GraphError, SCOPE, retry_not_before
from app.graph_deadline import request_deadline
from app.rotation_model import certificate_der, checked_candidate, key_record, proof, unique_json, uuid

LIMIT = 131072


class RotationGraph:
    def __init__(self, binding, signer, credential, http, *, deadline, clock=time.monotonic, wall=time.time, access=None):
        self.binding, self.signer, self.credential, self.http = binding, signer, credential, http
        self.deadline, self.clock, self.wall = deadline, clock, wall
        self.access=access
        self.root = "https://graph.microsoft.com/v1.0/applications/" + binding.application_id

    def _request(self, action, payload=None):
        if action not in {"read", "addKey", "removeKey"}:
            raise GraphError("rotation_action_invalid")
        writing = action != "read"
        seconds = min(45, self.deadline - self.clock())
        if seconds <= 0:
            raise GraphError("rotation_deadline", uncertain=False)
        try:
            with request_deadline(seconds, uncertain=writing):
                if self.access is not None:self.access.check(self.signer.pem,self.signer.fingerprint,method="POST" if writing else "GET")
                token = self.credential.get_token(SCOPE).token
                if not isinstance(token, str) or not token or any(c in token for c in "\r\n"):
                    raise GraphError("rotation_authentication_failed")
                headers = {"Authorization": "Bearer " + token, "Accept": "application/json",
                    "Content-Type": "application/json", "Accept-Encoding": "identity"}
                url = self.root if not writing else self.root + "/" + action
                params = {"$select": "id,appId,keyCredentials"} if not writing else None
                if self.access is not None:self.access.check(self.signer.pem,self.signer.fingerprint,method="POST" if writing else "GET")
                with self.http.stream("POST" if writing else "GET", url, params=params,
                        json=payload, headers=headers, follow_redirects=False) as response:
                    status = response.status_code
                    if status != (204 if action == "removeKey" else 200):
                        rejected = status in {400,401,403,404,405,413,415,422,429}
                        raise GraphError("rotation_registration_rejected" if writing and rejected else "rotation_http_error",
                            status, uncertain=writing and not rejected,
                            retry_not_before=retry_not_before(response.headers.get("Retry-After")) if status == 429 else None)
                    if action == "removeKey":
                        return None
                    if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
                        raise GraphError("rotation_response_invalid", uncertain=writing)
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        if len(raw) + len(chunk) > LIMIT:
                            raise GraphError("rotation_response_limit", uncertain=writing)
                        raw.extend(chunk)
                try:
                    result = json.loads(raw, object_pairs_hook=unique_json)
                    if not isinstance(result, dict):
                        raise ValueError()
                    return result
                except (ValueError, UnicodeError):
                    raise GraphError("rotation_response_invalid", uncertain=writing) from None
        except GraphError:
            raise
        except (httpx.HTTPError, OSError):
            raise GraphError("rotation_transport_error", uncertain=writing) from None
        except Exception:
            # Credential libraries never expose upstream text or cause a write retry.
            raise GraphError("rotation_runtime_unavailable", uncertain=writing) from None

    def read(self):
        value = self._request("read")
        if (value.get("id") != self.binding.application_id or value.get("appId") != self.binding.client_id
                or not isinstance(value.get("keyCredentials"), list) or len(value["keyCredentials"]) > 64):
            raise GraphError("rotation_app_binding_changed")
        records = [key_record(item) for item in value["keyCredentials"]]
        if len({item["key_id"] for item in records}) != len(records):
            raise GraphError("rotation_key_metadata_invalid")
        return records

    def add(self, material):
        checked_candidate(material, int(self.wall()))
        utc = lambda stamp: datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace("+00:00", "Z")
        value = self._request("addKey", dict(keyCredential=dict(type="AsymmetricX509Cert", usage="Verify",
            key=base64.b64encode(certificate_der(material)).decode("ascii"),
            startDateTime=utc(material.not_before), endDateTime=utc(material.expires_at)),
            passwordCredential=None, proof=proof(self.binding, self.signer, int(self.wall()))))
        try:
            # addKey need not echo public bytes; selected GET is the content proof.
            return uuid(value["keyId"])
        except (KeyError, GraphError):
            raise GraphError("rotation_response_invalid", uncertain=True) from None

    def remove(self, key_id):
        return self._request("removeKey", dict(keyId=uuid(key_id),
            proof=proof(self.binding, self.signer, int(self.wall()))))


@contextmanager
def rotation_client(binding, signer, *, deadline,access=None):
    """Host-core factory only; no HTTP/CLI route installs or invokes it in package B."""
    from azure.identity import CertificateCredential
    credential = CertificateCredential(binding.tenant_id, binding.client_id, certificate_data=signer.pem,
        retry_total=0, connection_timeout=5, read_timeout=10)
    try:
        with httpx.Client(timeout=httpx.Timeout(10, connect=5), trust_env=False,
                follow_redirects=False, limits=httpx.Limits(max_connections=1)) as http:
            yield RotationGraph(binding, signer, credential, http, deadline=deadline,access=access)
    finally:
        credential.close()
