"""
FHIR sandbag verification.

The script starts the FHIR MVP server on a local test port, exercises the
minimum Archon/PIT target surface, and terminates the server.

Usage:
  python test_fhir_verify.py
  python test_fhir_verify.py --port 18080
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
FHIR_JSON = "application/fhir+json"


class Result:
    def __init__(self, name: str) -> None:
        self.name = name
        self.passed = False
        self.detail = ""

    def ok(self, detail: str = "") -> None:
        self.passed = True
        self.detail = detail

    def fail(self, detail: str = "") -> None:
        self.passed = False
        self.detail = detail

    def __str__(self) -> str:
        tag = "PASS" if self.passed else "FAIL"
        return f"[{tag}] {self.name}" + (f" -- {self.detail}" if self.detail else "")


def request_json(method: str, url: str, body=None, headers=None):
    headers = dict(headers or {})
    headers.setdefault("Accept", FHIR_JSON)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", FHIR_JSON)
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=5) as response:
        payload = response.read()
        return response.status, response.headers, json.loads(payload.decode("utf-8"))


def request_form(method: str, url: str, form: dict[str, str], headers=None):
    headers = dict(headers or {})
    headers.setdefault("Accept", FHIR_JSON)
    headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    data = urlencode(form).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    with urlopen(request, timeout=5) as response:
        payload = response.read()
        return response.status, response.headers, json.loads(payload.decode("utf-8"))


def expect_http_error(method: str, url: str, expected_status: int, body=None, headers=None):
    try:
        request_json(method, url, body, headers)
    except HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        if exc.code != expected_status:
            raise AssertionError(f"expected {expected_status}, got {exc.code}: {payload}")
        if payload.get("resourceType") != "OperationOutcome":
            raise AssertionError(f"expected OperationOutcome, got {payload}")
        content_type = exc.headers.get("Content-Type", "")
        if not content_type.startswith(FHIR_JSON):
            raise AssertionError(f"expected {FHIR_JSON} content type, got {content_type}")
        return payload
    raise AssertionError(f"expected HTTP {expected_status}")


def wait_ready(base_url: str) -> None:
    deadline = time.time() + 15
    last_error = None
    while time.time() < deadline:
        try:
            status, _, body = request_json("GET", f"{base_url}/__health")
            if status == 200 and body.get("status") == "ok":
                return
        except (OSError, HTTPError, URLError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"FHIR sandbag did not become ready: {last_error}")


def tc_metadata(base_url: str) -> Result:
    result = Result("TC-1 metadata CapabilityStatement")
    try:
        status, _, body = request_json("GET", f"{base_url}/metadata")
        resources = {
            resource["type"]
            for rest in body.get("rest", [])
            for resource in rest.get("resource", [])
        }
        assert status == 200
        assert body["resourceType"] == "CapabilityStatement"
        assert body["fhirVersion"] == "4.0.1"
        assert {"Patient", "Observation"}.issubset(resources)
        result.ok("R4 Patient/Observation advertised")
    except Exception as exc:
        result.fail(str(exc))
    return result


def tc_patient_create_read_search(base_url: str) -> Result:
    result = Result("TC-2 Patient create/read/search")
    try:
        patient = {
            "resourceType": "Patient",
            "name": [{"family": "Lee", "given": ["Sora"]}],
            "identifier": [{"system": "urn:test", "value": "pit-patient"}],
        }
        status, headers, created = request_json("POST", f"{base_url}/Patient", patient)
        assert status == 201
        assert headers["Location"].endswith(f"/Patient/{created['id']}")
        status, _, read_back = request_json("GET", f"{base_url}/Patient/{created['id']}")
        assert status == 200
        assert read_back["name"][0]["family"] == "Lee"
        query = urlencode({"name": "Lee"})
        status, _, bundle = request_json("GET", f"{base_url}/Patient?{query}")
        assert status == 200
        assert bundle["resourceType"] == "Bundle"
        assert bundle["total"] >= 1
        status, _, form_bundle = request_form("POST", f"{base_url}/Patient/_search", {"identifier": "pit-patient"})
        assert status == 200
        assert form_bundle["resourceType"] == "Bundle"
        assert form_bundle["total"] >= 1
        token_query = urlencode({"identifier": "urn:test|pit-patient"})
        status, _, token_bundle = request_json("GET", f"{base_url}/Patient?{token_query}")
        assert status == 200
        assert token_bundle["resourceType"] == "Bundle"
        assert token_bundle["total"] >= 1
        result.ok(f"created id={created['id']}")
    except Exception as exc:
        result.fail(str(exc))
    return result


def tc_observation_update_search(base_url: str) -> Result:
    result = Result("TC-3 Observation create/update/search")
    try:
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
            "subject": {"reference": "Patient/example"},
            "valueQuantity": {"value": 72, "unit": "beats/min"},
        }
        status, _, created = request_json("POST", f"{base_url}/Observation", observation)
        assert status == 201
        created["valueQuantity"]["value"] = 73
        status, _, updated = request_json("PUT", f"{base_url}/Observation/{created['id']}", created)
        assert status == 200
        assert updated["meta"]["versionId"] == "2"
        query = urlencode({"code": "8867-4"})
        status, _, bundle = request_json("GET", f"{base_url}/Observation?{query}")
        assert status == 200
        assert bundle["total"] >= 1
        token_query = urlencode({"code": "http://loinc.org|8867-4"})
        status, _, token_bundle = request_json("GET", f"{base_url}/Observation?{token_query}")
        assert status == 200
        assert token_bundle["resourceType"] == "Bundle"
        assert token_bundle["total"] >= 1
        result.ok(f"updated id={created['id']}")
    except Exception as exc:
        result.fail(str(exc))
    return result


def tc_error_oracles(base_url: str) -> Result:
    result = Result("TC-4 OperationOutcome errors")
    try:
        expect_http_error("GET", f"{base_url}/Patient/not-found", 404)
        expect_http_error(
            "POST",
            f"{base_url}/Patient",
            415,
            {"resourceType": "Patient"},
            {"Content-Type": "text/plain", "Accept": FHIR_JSON},
        )
        expect_http_error(
            "POST",
            f"{base_url}/Patient",
            422,
            {"resourceType": "Observation"},
        )
        expect_http_error(
            "POST",
            f"{base_url}/Patient",
            400,
            {"resourceType": "Patient", "id": "bad/id"},
        )
        expect_http_error("PATCH", f"{base_url}/Patient/example", 405)
        expect_http_error("OPTIONS", f"{base_url}/metadata", 405)
        expect_http_error("GET", f"{base_url.rstrip('/')}Patient", 404)
        request = Request(
            f"{base_url}/Patient",
            data=b"{not-json",
            headers={"Content-Type": FHIR_JSON, "Accept": FHIR_JSON},
            method="POST",
        )
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 400
            assert body["resourceType"] == "OperationOutcome"
        else:
            raise AssertionError("expected invalid JSON to fail")
        result.ok("404/415/422/405/400 returned OperationOutcome")
    except Exception as exc:
        result.fail(str(exc))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="FHIR sandbag verification")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--base-path", default="/fhir")
    args = parser.parse_args()

    base_url = f"http://127.0.0.1:{args.port}{args.base_path.rstrip('/')}"
    cmd = [
        sys.executable,
        str(ROOT / "services" / "fhir_service.py"),
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--base-path",
        args.base_path,
    ]
    proc = subprocess.Popen(cmd, cwd=str(ROOT))
    try:
        wait_ready(base_url)
        if proc.poll() is not None:
            raise RuntimeError(f"FHIR sandbag process exited early with code {proc.returncode}")
        results = [
            tc_metadata(base_url),
            tc_patient_create_read_search(base_url),
            tc_observation_update_search(base_url),
            tc_error_oracles(base_url),
        ]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    print("=" * 60)
    print("  FHIR Sandbag Verification")
    print("=" * 60)
    for result in results:
        print(f"  {result}")
    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    print()
    print(f"  Total: {len(results)}   Passed: {passed}   Failed: {failed}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
