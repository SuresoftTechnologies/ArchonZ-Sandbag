"""
FHIR external target verification.

This script verifies a running FHIR R4 endpoint such as a local HAPI FHIR
server. It does not start Sandbag. Write checks are disabled by default so the
script can be used safely for read-only smoke checks.

Usage:
  python test_fhir_target_verify.py --base-url http://127.0.0.1:8090/fhir
  python test_fhir_target_verify.py --base-url http://127.0.0.1:8090/fhir --allow-write
  python test_fhir_target_verify.py --base-url https://hapi.fhir.org/baseR4 --skip-swagger
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


FHIR_JSON = "application/fhir+json"


@dataclass
class Result:
    name: str
    status: str = "FAIL"
    detail: str = ""

    def pass_(self, detail: str = "") -> None:
        self.status = "PASS"
        self.detail = detail

    def skip(self, detail: str = "") -> None:
        self.status = "SKIP"
        self.detail = detail

    def fail(self, detail: str = "") -> None:
        self.status = "FAIL"
        self.detail = detail

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"

    def __str__(self) -> str:
        suffix = f" -- {self.detail}" if self.detail else ""
        return f"[{self.status}] {self.name}{suffix}"


def join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def is_local_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.startswith("127.")


def request(method: str, url: str, body=None, headers=None, timeout: int = 10):
    headers = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers.setdefault("Content-Type", FHIR_JSON)
    request_obj = Request(url, data=data, headers=headers, method=method)
    with urlopen(request_obj, timeout=timeout) as response:
        return response.status, response.headers, response.read()


def request_json(method: str, url: str, body=None, headers=None, timeout: int = 10):
    headers = dict(headers or {})
    headers.setdefault("Accept", FHIR_JSON)
    status, response_headers, payload = request(method, url, body, headers, timeout)
    text = payload.decode("utf-8")
    return status, response_headers, json.loads(text) if text else {}


def wait_metadata(base_url: str, timeout: int) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            status, _, body = request_json("GET", join_url(base_url, "metadata"), timeout=timeout)
            if status == 200 and body.get("resourceType") == "CapabilityStatement":
                return
        except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"FHIR endpoint did not become ready: {last_error}")


def tc_metadata(base_url: str, timeout: int) -> Result:
    result = Result("metadata CapabilityStatement")
    try:
        status, headers, body = request_json("GET", join_url(base_url, "metadata"), timeout=timeout)
        resources = {
            resource["type"]
            for rest in body.get("rest", [])
            for resource in rest.get("resource", [])
            if "type" in resource
        }
        content_type = headers.get("Content-Type", "")
        check(status == 200, f"expected HTTP 200, got {status}")
        check(body.get("resourceType") == "CapabilityStatement", f"expected CapabilityStatement, got {body.get('resourceType')}")
        check(body.get("fhirVersion") == "4.0.1", f"expected FHIR 4.0.1, got {body.get('fhirVersion')}")
        check({"Patient", "Observation"}.issubset(resources), f"missing Patient/Observation in resources: {sorted(resources)}")
        result.pass_(f"FHIR {body.get('fhirVersion')} resources={','.join(sorted(resources & {'Patient', 'Observation'}))} content-type={content_type}")
    except Exception as exc:
        result.fail(str(exc))
    return result


def tc_readonly_search(base_url: str, timeout: int) -> Result:
    result = Result("read-only Patient/Observation search")
    try:
        checks = [
            ("Patient", join_url(base_url, "Patient?_count=1")),
            ("Observation", join_url(base_url, "Observation?_count=1")),
        ]
        totals: list[str] = []
        for resource_type, url in checks:
            status, _, body = request_json("GET", url, timeout=timeout)
            check(status == 200, f"{resource_type} search expected HTTP 200, got {status}")
            check(body.get("resourceType") == "Bundle", f"{resource_type} search expected Bundle, got {body.get('resourceType')}")
            totals.append(f"{resource_type}:{body.get('total', 'unknown')}")
        result.pass_(", ".join(totals))
    except Exception as exc:
        result.fail(str(exc))
    return result


def tc_swagger(base_url: str, timeout: int) -> Result:
    result = Result("HAPI Swagger/OpenAPI endpoints")
    try:
        status, api_headers, api_payload = request(
            "GET",
            join_url(base_url, "api-docs"),
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        check(status == 200, f"expected /api-docs HTTP 200, got {status}")
        api_text = api_payload[:4096].decode("utf-8", errors="replace")
        openapi_version = ""
        try:
            api_docs = json.loads(api_payload.decode("utf-8"))
            openapi_version = str(api_docs.get("openapi") or api_docs.get("swagger") or "")
        except json.JSONDecodeError:
            if not ("openapi:" in api_text.lower() or "swagger:" in api_text.lower()):
                raise
            first_line = api_text.strip().splitlines()[0]
            openapi_version = first_line.replace("openapi:", "").replace("swagger:", "").strip()

        status, headers, html = request(
            "GET",
            join_url(base_url, "swagger-ui/"),
            headers={"Accept": "text/html,application/xhtml+xml"},
            timeout=timeout,
        )
        text = html[:4096].decode("utf-8", errors="replace")
        check(status == 200, f"expected /swagger-ui/ HTTP 200, got {status}")
        check("swagger" in text.lower() or "openapi" in text.lower(), "swagger UI response did not contain swagger/openapi text")
        result.pass_(f"api-docs version={openapi_version} api-content-type={api_headers.get('Content-Type', '')} ui-content-type={headers.get('Content-Type', '')}")
    except Exception as exc:
        result.fail(str(exc))
    return result


def tc_write_roundtrip(base_url: str, timeout: int) -> Result:
    result = Result("write roundtrip Patient/Observation")
    patient_id = None
    observation_id = None
    unique = uuid.uuid4().hex
    try:
        identifier = f"archon-hapi-target-{unique}"
        patient = {
            "resourceType": "Patient",
            "identifier": [{"system": "urn:archon:fhir:hapi-target", "value": identifier}],
            "name": [{"family": "ArchonHapiTarget", "given": [unique[:8]]}],
            "gender": "unknown",
            "active": True,
        }
        status, headers, created_patient = request_json(
            "POST",
            join_url(base_url, "Patient"),
            patient,
            timeout=timeout,
        )
        check(status == 201, f"Patient create expected HTTP 201, got {status}")
        patient_id = created_patient["id"]
        check(bool(headers.get("Location") or headers.get("Content-Location")), "Patient create response missing Location/Content-Location")

        status, _, read_patient = request_json("GET", join_url(base_url, f"Patient/{patient_id}"), timeout=timeout)
        check(status == 200, f"Patient read expected HTTP 200, got {status}")
        check(read_patient.get("resourceType") == "Patient", f"Patient read expected Patient, got {read_patient.get('resourceType')}")

        query = urlencode({"identifier": f"urn:archon:fhir:hapi-target|{identifier}"})
        status, _, bundle = request_json("GET", join_url(base_url, f"Patient?{query}"), timeout=timeout)
        check(status == 200, f"Patient identifier search expected HTTP 200, got {status}")
        check(bundle.get("resourceType") == "Bundle", f"Patient identifier search expected Bundle, got {bundle.get('resourceType')}")
        check(bundle.get("total", 0) >= 1, f"Patient identifier search expected at least 1 result, got {bundle.get('total')}")

        observation = {
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}], "text": "Body temperature"},
            "subject": {"reference": f"Patient/{patient_id}"},
            "valueQuantity": {"value": 36.7, "unit": "Cel", "system": "http://unitsofmeasure.org", "code": "Cel"},
        }
        status, _, created_observation = request_json(
            "POST",
            join_url(base_url, "Observation"),
            observation,
            timeout=timeout,
        )
        check(status == 201, f"Observation create expected HTTP 201, got {status}")
        observation_id = created_observation["id"]

        subject_query = urlencode({"subject": f"Patient/{patient_id}"})
        status, _, obs_bundle = request_json("GET", join_url(base_url, f"Observation?{subject_query}"), timeout=timeout)
        check(status == 200, f"Observation subject search expected HTTP 200, got {status}")
        check(obs_bundle.get("resourceType") == "Bundle", f"Observation subject search expected Bundle, got {obs_bundle.get('resourceType')}")
        check(obs_bundle.get("total", 0) >= 1, f"Observation subject search expected at least 1 result, got {obs_bundle.get('total')}")

        result.pass_(f"patient={patient_id} observation={observation_id}")
    except Exception as exc:
        result.fail(str(exc))
    finally:
        # Best-effort cleanup for local HAPI runs. Some servers return JSON,
        # others return an empty 204; either way cleanup must not mask test output.
        for resource_type, resource_id in (("Observation", observation_id), ("Patient", patient_id)):
            if resource_id:
                try:
                    request("DELETE", join_url(base_url, f"{resource_type}/{resource_id}"), timeout=timeout)
                except Exception:
                    pass
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="FHIR R4 external target verification")
    parser.add_argument("--base-url", required=True, help="FHIR service base URL, e.g. http://127.0.0.1:8090/fhir")
    parser.add_argument("--allow-write", action="store_true", help="Run create/read/search checks against the target")
    parser.add_argument(
        "--allow-non-local-write",
        action="store_true",
        help="Permit --allow-write against a non-localhost target. Use only for explicitly authorized private targets.",
    )
    parser.add_argument("--skip-swagger", action="store_true", help="Skip /api-docs and /swagger-ui/ checks")
    parser.add_argument("--ready-timeout", type=int, default=30, help="Seconds to wait for /metadata to become ready")
    parser.add_argument("--request-timeout", type=int, default=15, help="Per-request timeout in seconds")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    if args.allow_write and not is_local_url(base_url) and not args.allow_non_local_write:
        print(
            "Refusing write checks against a non-local target. Use local HAPI, or add "
            "--allow-non-local-write only for an explicitly authorized private target.",
            file=sys.stderr,
        )
        return 2
    wait_metadata(base_url, args.ready_timeout)

    results = [
        tc_metadata(base_url, args.request_timeout),
        tc_readonly_search(base_url, args.request_timeout),
    ]
    if args.skip_swagger:
        skipped = Result("HAPI Swagger/OpenAPI endpoints")
        skipped.skip("skipped by --skip-swagger")
        results.append(skipped)
    else:
        results.append(tc_swagger(base_url, args.request_timeout))

    if args.allow_write:
        results.append(tc_write_roundtrip(base_url, args.request_timeout))
    else:
        skipped = Result("write roundtrip Patient/Observation")
        skipped.skip("use --allow-write for local authorized targets")
        results.append(skipped)

    print("=" * 72)
    print("  FHIR External Target Verification")
    print("=" * 72)
    print(f"  Base URL: {base_url}")
    print()
    for result in results:
        print(f"  {result}")
    failed = sum(1 for result in results if result.failed)
    skipped = sum(1 for result in results if result.status == "SKIP")
    passed = len(results) - failed - skipped
    print()
    print(f"  Total: {len(results)}   Passed: {passed}   Skipped: {skipped}   Failed: {failed}")
    print("=" * 72)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
