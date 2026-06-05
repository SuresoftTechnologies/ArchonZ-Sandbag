from __future__ import annotations

import argparse
import copy
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


FHIR_VERSION = "4.0.1"
FHIR_JSON = "application/fhir+json"
MAX_BODY_BYTES = 1024 * 1024
SUPPORTED_TYPES = ("Patient", "Observation")
FHIR_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,63}$")

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _seed_resources() -> dict[str, dict[str, dict[str, Any]]]:
    patient = {
        "resourceType": "Patient",
        "id": "example",
        "meta": {"versionId": "1", "lastUpdated": _now()},
        "identifier": [
            {
                "system": "urn:archonz-sandbag:patient-id",
                "value": "patient-example",
            }
        ],
        "name": [{"family": "Kim", "given": ["Minsoo"]}],
        "gender": "male",
        "birthDate": "1990-01-01",
        "active": True,
    }
    observation = {
        "resourceType": "Observation",
        "id": "example",
        "meta": {"versionId": "1", "lastUpdated": _now()},
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "8310-5",
                    "display": "Body temperature",
                }
            ],
            "text": "Body temperature",
        },
        "subject": {"reference": "Patient/example"},
        "valueQuantity": {
            "value": 36.7,
            "unit": "Cel",
            "system": "http://unitsofmeasure.org",
            "code": "Cel",
        },
    }
    return {
        "Patient": {"example": patient},
        "Observation": {"example": observation},
    }


class FHIRStore:
    def __init__(self) -> None:
        self.resources = _seed_resources()

    def get(self, resource_type: str, resource_id: str) -> dict[str, Any] | None:
        resource = self.resources.get(resource_type, {}).get(resource_id)
        return copy.deepcopy(resource) if resource else None

    def put(self, resource_type: str, resource_id: str, resource: dict[str, Any]) -> dict[str, Any]:
        bucket = self.resources.setdefault(resource_type, {})
        existing = bucket.get(resource_id)
        version = int(existing.get("meta", {}).get("versionId", "0")) + 1 if existing else 1
        stored = copy.deepcopy(resource)
        stored["resourceType"] = resource_type
        stored["id"] = resource_id
        stored.setdefault("meta", {})
        stored["meta"]["versionId"] = str(version)
        stored["meta"]["lastUpdated"] = _now()
        bucket[resource_id] = stored
        return copy.deepcopy(stored)

    def create(self, resource_type: str, resource: dict[str, Any]) -> dict[str, Any]:
        resource_id = str(resource.get("id") or uuid.uuid4())
        while resource_id in self.resources.setdefault(resource_type, {}):
            resource_id = str(uuid.uuid4())
        return self.put(resource_type, resource_id, resource)

    def search(self, resource_type: str, query: dict[str, list[str]]) -> list[dict[str, Any]]:
        values = list(self.resources.get(resource_type, {}).values())
        if resource_type == "Patient":
            name_filters = [v.lower() for v in query.get("name", []) if v]
            identifier_filters = [v.lower() for v in query.get("identifier", []) if v]
            if name_filters:
                values = [
                    r
                    for r in values
                    if any(_patient_matches_name(r, term) for term in name_filters)
                ]
            if identifier_filters:
                values = [
                    r
                    for r in values
                    if any(_resource_has_identifier(r, term) for term in identifier_filters)
                ]
        elif resource_type == "Observation":
            code_filters = [v.lower() for v in query.get("code", []) if v]
            subject_filters = [v.lower() for v in query.get("subject", []) if v]
            if code_filters:
                values = [
                    r
                    for r in values
                    if any(_observation_matches_code(r, term) for term in code_filters)
                ]
            if subject_filters:
                values = [
                    r
                    for r in values
                    if any(_observation_matches_subject(r, term) for term in subject_filters)
                ]
        return [copy.deepcopy(v) for v in values]


def _patient_matches_name(resource: dict[str, Any], term: str) -> bool:
    for name in resource.get("name", []):
        parts = [name.get("family", "")]
        parts.extend(name.get("given", []))
        if term in " ".join(parts).lower():
            return True
    return False


def _resource_has_identifier(resource: dict[str, Any], term: str) -> bool:
    system, value = _split_token(term)
    for identifier in resource.get("identifier", []):
        candidate_system = str(identifier.get("system", "")).lower()
        candidate_value = str(identifier.get("value", "")).lower()
        if system is not None and candidate_system != system:
            continue
        if value is None:
            return True
        if value in candidate_value:
            return True
    return False


def _observation_matches_code(resource: dict[str, Any], term: str) -> bool:
    system, value = _split_token(term)
    code = resource.get("code", {})
    if system is None and value and value in str(code.get("text", "")).lower():
        return True
    for coding in code.get("coding", []):
        candidate_system = str(coding.get("system", "")).lower()
        candidate_code = str(coding.get("code", "")).lower()
        if system is not None and candidate_system != system:
            continue
        if value is None:
            return True
        if value in candidate_code:
            return True
    return False


def _observation_matches_subject(resource: dict[str, Any], term: str) -> bool:
    return term in str(resource.get("subject", {}).get("reference", "")).lower()


def _split_token(term: str) -> tuple[str | None, str | None]:
    if "|" not in term:
        return None, term
    system, value = term.split("|", 1)
    return system or None, value or None


def _resource_id_is_valid(resource_id: str) -> bool:
    return bool(FHIR_ID_RE.fullmatch(resource_id))


def _operation_outcome(
    diagnostics: str,
    code: str = "processing",
    severity: str = "error",
) -> dict[str, Any]:
    return {
        "resourceType": "OperationOutcome",
        "issue": [
            {
                "severity": severity,
                "code": code,
                "diagnostics": diagnostics,
            }
        ],
    }


def _bundle(base_url: str, resource_type: str, resources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(resources),
        "link": [{"relation": "self", "url": f"{base_url}/{resource_type}"}],
        "entry": [
            {
                "fullUrl": f"{base_url}/{resource_type}/{resource['id']}",
                "resource": resource,
            }
            for resource in resources
        ],
    }


def _capability_statement(base_url: str) -> dict[str, Any]:
    resources = []
    for resource_type in SUPPORTED_TYPES:
        search_params = []
        if resource_type == "Patient":
            search_params = [
                {"name": "name", "type": "string"},
                {"name": "identifier", "type": "token"},
            ]
        elif resource_type == "Observation":
            search_params = [
                {"name": "code", "type": "token"},
                {"name": "subject", "type": "reference"},
            ]
        resources.append(
            {
                "type": resource_type,
                "interaction": [
                    {"code": "read"},
                    {"code": "create"},
                    {"code": "update"},
                    {"code": "search-type"},
                ],
                "searchParam": search_params,
            }
        )
    return {
        "resourceType": "CapabilityStatement",
        "id": "archonz-sandbag-fhir",
        "url": f"{base_url}/metadata",
        "version": "0.1.0",
        "name": "ArchonZSandbagFHIR",
        "title": "ArchonZ Sandbag FHIR MVP",
        "status": "draft",
        "date": _now(),
        "kind": "instance",
        "software": {"name": "ArchonZ-Sandbag FHIR Service", "version": "0.1.0"},
        "implementation": {
            "description": "Synthetic FHIR R4 target for Archon/PIT fuzzing",
            "url": base_url,
        },
        "fhirVersion": FHIR_VERSION,
        "format": ["json"],
        "rest": [
            {
                "mode": "server",
                "resource": resources,
            }
        ],
    }


class FHIRRequestHandler(BaseHTTPRequestHandler):
    server: "FHIRHTTPServer"

    def log_message(self, format: str, *args: object) -> None:
        logger.info("%s - %s", self.address_string(), format % args)

    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_HEAD(self) -> None:
        self._handle_request("HEAD")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def do_PUT(self) -> None:
        self._handle_request("PUT")

    def do_PATCH(self) -> None:
        self._handle_request("PATCH")

    def do_DELETE(self) -> None:
        self._send_outcome(HTTPStatus.METHOD_NOT_ALLOWED, "delete is not supported by this MVP")

    def do_OPTIONS(self) -> None:
        self._send_outcome(HTTPStatus.METHOD_NOT_ALLOWED, "options is not supported by this MVP")

    def do_TRACE(self) -> None:
        self._send_outcome(HTTPStatus.METHOD_NOT_ALLOWED, "trace is not supported by this MVP")

    def send_error(
        self,
        code: int,
        message: str | None = None,
        explain: str | None = None,
    ) -> None:
        try:
            status = HTTPStatus(code)
        except ValueError:
            status = HTTPStatus.INTERNAL_SERVER_ERROR
        diagnostics = message or explain or status.phrase
        self._send_outcome(status, diagnostics)

    def _handle_request(self, method: str) -> None:
        try:
            parsed = urlparse(self.path)
            parts = self._path_parts(parsed.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            if self._format_is_unacceptable(query):
                self._send_outcome(
                    HTTPStatus.NOT_ACCEPTABLE,
                    "Only application/fhir+json responses are supported",
                    "not-supported",
                )
                return
            if parts == ["__health"]:
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return
            if parts == ["metadata"] and method in ("GET", "HEAD"):
                self._send_json(HTTPStatus.OK, _capability_statement(self._base_url()), head=method == "HEAD")
                return
            if method == "POST" and parts == [""]:
                self._send_outcome(
                    HTTPStatus.BAD_REQUEST,
                    "batch/transaction Bundle is not implemented in this MVP",
                    "not-supported",
                )
                return
            if len(parts) == 2 and parts[0] in SUPPORTED_TYPES and parts[1] == "_search":
                self._handle_search(method, parts[0], query)
                return
            if len(parts) == 1 and parts[0] in SUPPORTED_TYPES:
                self._handle_collection(method, parts[0], query)
                return
            if len(parts) == 2 and parts[0] in SUPPORTED_TYPES:
                self._handle_instance(method, parts[0], parts[1])
                return
            self._send_outcome(HTTPStatus.NOT_FOUND, f"Unsupported FHIR path: {parsed.path}", "not-found")
        except Exception as exc:
            logger.exception("FHIR request failed")
            self._send_outcome(HTTPStatus.INTERNAL_SERVER_ERROR, f"internal error: {exc}")

    def _handle_collection(
        self,
        method: str,
        resource_type: str,
        query: dict[str, list[str]],
    ) -> None:
        if method == "GET":
            resources = self.server.store.search(resource_type, query)
            self._send_json(HTTPStatus.OK, _bundle(self._base_url(), resource_type, resources))
            return
        if method == "POST":
            resource = self._read_resource_body(resource_type)
            if resource is None:
                return
            resource_id = resource.get("id")
            if resource_id and not _resource_id_is_valid(str(resource_id)):
                self._send_outcome(HTTPStatus.BAD_REQUEST, "resource id is not a valid FHIR logical id", "invalid")
                return
            stored = self.server.store.create(resource_type, resource)
            self._send_json(
                HTTPStatus.CREATED,
                stored,
                extra_headers={
                    "Location": f"{self._base_url()}/{resource_type}/{stored['id']}",
                    "ETag": f"W/\"{stored['meta']['versionId']}\"",
                    "Last-Modified": _http_date(stored["meta"]["lastUpdated"]),
                },
            )
            return
        self._send_outcome(HTTPStatus.METHOD_NOT_ALLOWED, f"{method} is not supported on {resource_type}")

    def _handle_search(
        self,
        method: str,
        resource_type: str,
        query: dict[str, list[str]],
    ) -> None:
        if method == "GET":
            resources = self.server.store.search(resource_type, query)
            self._send_json(HTTPStatus.OK, _bundle(self._base_url(), resource_type, resources))
            return
        if method != "POST":
            self._send_outcome(HTTPStatus.METHOD_NOT_ALLOWED, f"{method} is not supported on {resource_type}/_search")
            return

        body_query = self._read_search_body()
        if body_query is None:
            return
        merged_query = dict(query)
        for key, values in body_query.items():
            merged_query.setdefault(key, []).extend(values)
        resources = self.server.store.search(resource_type, merged_query)
        self._send_json(HTTPStatus.OK, _bundle(self._base_url(), resource_type, resources))

    def _handle_instance(self, method: str, resource_type: str, resource_id: str) -> None:
        resource_id = unquote(resource_id)
        if not _resource_id_is_valid(resource_id):
            self._send_outcome(HTTPStatus.BAD_REQUEST, "resource id is not a valid FHIR logical id", "invalid")
            return
        if method in ("GET", "HEAD"):
            resource = self.server.store.get(resource_type, resource_id)
            if resource is None:
                self._send_outcome(
                    HTTPStatus.NOT_FOUND,
                    f"{resource_type}/{resource_id} was not found",
                    "not-found",
                )
                return
            self._send_json(
                HTTPStatus.OK,
                resource,
                extra_headers={
                    "ETag": f"W/\"{resource.get('meta', {}).get('versionId', '1')}\"",
                    "Last-Modified": _http_date(resource.get("meta", {}).get("lastUpdated", _now())),
                },
                head=method == "HEAD",
            )
            return
        if method == "PUT":
            resource = self._read_resource_body(resource_type)
            if resource is None:
                return
            if resource.get("id") and resource["id"] != resource_id:
                self._send_outcome(
                    HTTPStatus.BAD_REQUEST,
                    "resource id does not match URL id",
                    "invalid",
                )
                return
            stored = self.server.store.put(resource_type, resource_id, resource)
            self._send_json(
                HTTPStatus.OK,
                stored,
                extra_headers={
                    "ETag": f"W/\"{stored['meta']['versionId']}\"",
                    "Last-Modified": _http_date(stored["meta"]["lastUpdated"]),
                },
            )
            return
        self._send_outcome(HTTPStatus.METHOD_NOT_ALLOWED, f"{method} is not supported on {resource_type}/{resource_id}")

    def _read_resource_body(self, expected_type: str) -> dict[str, Any] | None:
        if not self._request_content_type_supported():
            self._drain_request_body()
            self._send_outcome(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "Use Content-Type: application/fhir+json",
                "not-supported",
            )
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_outcome(HTTPStatus.BAD_REQUEST, "invalid Content-Length", "invalid")
            return None
        if length <= 0:
            self._send_outcome(HTTPStatus.BAD_REQUEST, "request body is required", "required")
            return None
        if length > self.server.max_body_bytes:
            self._send_outcome(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body is too large", "too-costly")
            return None
        raw = self.rfile.read(length)
        try:
            resource = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_outcome(HTTPStatus.BAD_REQUEST, f"invalid FHIR JSON: {exc}", "invalid")
            return None
        if not isinstance(resource, dict):
            self._send_outcome(HTTPStatus.BAD_REQUEST, "FHIR resource must be a JSON object", "invalid")
            return None
        actual_type = resource.get("resourceType")
        if actual_type != expected_type:
            self._send_outcome(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"resourceType must be {expected_type}, got {actual_type!r}",
                "invalid",
            )
            return None
        return resource

    def _path_parts(self, raw_path: str) -> list[str]:
        base_path = self.server.base_path.rstrip("/")
        path = raw_path.rstrip("/") or "/"
        if base_path and path == base_path:
            path = "/"
        elif base_path and path.startswith(f"{base_path}/"):
            path = path[len(base_path) :] or "/"
        elif base_path:
            return ["__not_under_base__", raw_path]
        if path == "/":
            return [""]
        return [unquote(p) for p in path.lstrip("/").split("/")]

    def _base_url(self) -> str:
        host = self.headers.get("Host") or f"{self.server.host}:{self.server.port}"
        scheme = "https" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else "http"
        return f"{scheme}://{host}{self.server.base_path.rstrip('/')}"

    def _request_content_type_supported(self) -> bool:
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        return content_type in (FHIR_JSON, "application/json")

    def _read_search_body(self) -> dict[str, list[str]] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_outcome(HTTPStatus.BAD_REQUEST, "invalid Content-Length", "invalid")
            return None
        if length == 0:
            return {}
        if length > self.server.max_body_bytes:
            self._send_outcome(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body is too large", "too-costly")
            return None
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            self._drain_request_body(length)
            self._send_outcome(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "Use Content-Type: application/x-www-form-urlencoded for _search",
                "not-supported",
            )
            return None
        raw = self.rfile.read(length)
        try:
            return parse_qs(raw.decode("utf-8"), keep_blank_values=True)
        except UnicodeDecodeError as exc:
            self._send_outcome(HTTPStatus.BAD_REQUEST, f"invalid search form body: {exc}", "invalid")
            return None

    def _drain_request_body(self, known_length: int | None = None) -> None:
        try:
            length = known_length if known_length is not None else int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return
        if length <= 0:
            return
        remaining = min(length, self.server.max_body_bytes)
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 8192))
            if not chunk:
                return
            remaining -= len(chunk)

    def _format_is_unacceptable(self, query: dict[str, list[str]]) -> bool:
        requested = query.get("_format", [])
        if requested and not any(_is_json_format(v) for v in requested):
            return True
        accept = self.headers.get("Accept", "")
        if not accept:
            return False
        return not any(_accept_token_supported(token) for token in accept.split(","))

    def _send_outcome(self, status: HTTPStatus, diagnostics: str, code: str = "processing") -> None:
        self._send_json(status, _operation_outcome(diagnostics, code))

    def _send_json(
        self,
        status: HTTPStatus,
        body: dict[str, Any],
        extra_headers: dict[str, str] | None = None,
        head: bool = False,
    ) -> None:
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status.value, status.phrase)
        self.send_header("Content-Type", f"{FHIR_JSON}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-ArchonZ-Sandbag", "fhir-r4-mvp")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        if not head:
            self.wfile.write(payload)


def _accept_token_supported(token: str) -> bool:
    media_type = token.split(";")[0].strip().lower()
    return media_type in ("", "*/*", "application/*", FHIR_JSON, "application/json")


def _is_json_format(value: str) -> bool:
    value = value.lower()
    return value in ("json", FHIR_JSON, "application/json") or value.endswith("fhir+json")


def _http_date(instant: str) -> str:
    try:
        dt = datetime.fromisoformat(instant.replace("Z", "+00:00"))
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", dt.utctimetuple())
    except ValueError:
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())


class FHIRHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        base_path: str,
        max_body_bytes: int,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.host = server_address[0]
        self.port = server_address[1]
        self.base_path = "/" + base_path.strip("/") if base_path and base_path != "/" else ""
        self.max_body_bytes = max_body_bytes
        self.store = FHIRStore()


def run_fhir(host: str = "0.0.0.0", port: int = 8080, base_path: str = "/fhir") -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
    server = FHIRHTTPServer(
        (host, port),
        FHIRRequestHandler,
        base_path=base_path,
        max_body_bytes=MAX_BODY_BYTES,
    )
    logger.info("FHIR sandbag listening on http://%s:%s%s", host, port, server.base_path)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        logger.info("FHIR sandbag stopped")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("fhir-sandbag")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--base-path", default="/fhir")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_fhir(args.host, args.port, args.base_path)
