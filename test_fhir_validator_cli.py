#!/usr/bin/env python3
"""Thin wrapper around the HL7 FHIR validator CLI for KR Core oracle checks.

The validator JAR and KR Core package are intentionally external inputs. This
script normalizes validator setup, OperationOutcome parsing, and exit policy so
Archon can record KR profile results separately from HAPI runtime behavior.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FHIR_VERSION = "4.0.1"
KR_CORE_IG = "hl7.fhir.kr.core#2.0.0"
PATIENT_PROFILE = "http://www.hl7korea.or.kr/fhir/krcore/StructureDefinition/krcore-patient"
BODY_TEMPERATURE_PROFILE = "http://www.hl7korea.or.kr/fhir/krcore/StructureDefinition/krcore-bodytemperature"

VALID_PROFILE_PASS = "VALID_PROFILE_PASS"
EXPECTED_INVALID = "EXPECTED_INVALID"
PROFILE_ERROR = "PROFILE_ERROR"
TARGET_ACCEPTED_INVALID = "TARGET_ACCEPTED_INVALID"
TARGET_REJECTED_VALID = "TARGET_REJECTED_VALID"
TARGET_FAULT = "TARGET_FAULT"
INCONCLUSIVE_ORACLE = "INCONCLUSIVE_ORACLE"

ERROR_SEVERITIES = {"fatal", "error"}


@dataclass
class OracleResult:
    result_class: str
    exit_code: int
    errors: int = 0
    warnings: int = 0
    information: int = 0
    diagnostics: list[str] | None = None
    detail: str = ""
    validator_command: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "result_class": self.result_class,
            "exit_code": self.exit_code,
            "errors": self.errors,
            "warnings": self.warnings,
            "information": self.information,
            "diagnostics": self.diagnostics or [],
            "detail": self.detail,
            "validator_command": self.validator_command or [],
        }


def load_resource(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_json_body(raw_http: str) -> dict[str, Any]:
    separator = "\r\n\r\n" if "\r\n\r\n" in raw_http else "\n\n"
    _, _, body = raw_http.partition(separator)
    if not body:
        body = raw_http
    return json.loads(body.strip())


def profile_for_resource(resource: dict[str, Any]) -> str | None:
    resource_type = resource.get("resourceType")
    if resource_type == "Patient":
        return PATIENT_PROFILE
    if resource_type == "Observation":
        profiles = resource.get("meta", {}).get("profile", [])
        if BODY_TEMPERATURE_PROFILE in profiles:
            return BODY_TEMPERATURE_PROFILE
        code = resource.get("code", {})
        for coding in code.get("coding", []):
            if coding.get("system") == "http://loinc.org" and coding.get("code") == "8310-5":
                return BODY_TEMPERATURE_PROFILE
    return None


def summarize_operation_outcome(outcome: dict[str, Any]) -> tuple[int, int, int, list[str]]:
    errors = 0
    warnings = 0
    information = 0
    diagnostics: list[str] = []
    for issue in outcome.get("issue", []):
        severity = str(issue.get("severity", "")).lower()
        if severity in ERROR_SEVERITIES:
            errors += 1
        elif severity == "warning":
            warnings += 1
        elif severity == "information":
            information += 1
        diagnostic = issue.get("diagnostics")
        if diagnostic:
            diagnostics.append(str(diagnostic))
    return errors, warnings, information, diagnostics


def classify_validation(
    validator_exit_code: int,
    outcome: dict[str, Any] | None,
    expected: str,
    strict_warnings: bool,
) -> OracleResult:
    errors = 0
    warnings = 0
    information = 0
    diagnostics: list[str] = []
    if outcome:
        errors, warnings, information, diagnostics = summarize_operation_outcome(outcome)

    has_profile_error = validator_exit_code != 0 or errors > 0 or (strict_warnings and warnings > 0)
    if expected == "invalid" and has_profile_error:
        result_class = EXPECTED_INVALID
        exit_code = 0
    elif expected == "valid" and has_profile_error:
        result_class = PROFILE_ERROR
        exit_code = 1
    elif expected == "any" and has_profile_error:
        result_class = PROFILE_ERROR
        exit_code = 0
    else:
        result_class = VALID_PROFILE_PASS
        exit_code = 0

    return OracleResult(
        result_class=result_class,
        exit_code=exit_code,
        errors=errors,
        warnings=warnings,
        information=information,
        diagnostics=diagnostics,
        detail=f"validator_exit_code={validator_exit_code}",
    )


def build_validator_command(
    java_path: str,
    validator_jar: Path,
    resource_path: Path,
    output_path: Path,
    version: str,
    ig: str | None,
    profile: str | None,
    tx: str | None,
) -> list[str]:
    command = [
        java_path,
        "-jar",
        str(validator_jar),
        str(resource_path),
        "-version",
        version,
        "-output",
        str(output_path),
    ]
    if tx:
        command.extend(["-tx", tx])
    if ig:
        command.extend(["-ig", ig])
    if profile:
        command.extend(["-profile", profile])
    return command


def read_outcome(output_path: Path, stdout: str) -> dict[str, Any] | None:
    candidates = []
    if output_path.exists() and output_path.stat().st_size > 0:
        candidates.append(output_path.read_text(encoding="utf-8"))
    if stdout.strip().startswith("{"):
        candidates.append(stdout)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if parsed.get("resourceType") == "OperationOutcome":
            return parsed
    return None


def setup_failure(message: str, monitor_mode: bool) -> OracleResult:
    return OracleResult(
        result_class=INCONCLUSIVE_ORACLE,
        exit_code=0 if monitor_mode else 2,
        detail=message,
    )


def validate_resource(args: argparse.Namespace) -> OracleResult:
    validator_jar_text = args.validator_jar or os.environ.get("FHIR_VALIDATOR_CLI_JAR")
    if not validator_jar_text:
        return setup_failure("validator jar not provided; use --validator-jar or FHIR_VALIDATOR_CLI_JAR", args.monitor_mode)

    validator_jar = Path(validator_jar_text)
    if not validator_jar.is_file():
        return setup_failure(f"validator jar not found: {validator_jar}", args.monitor_mode)

    if args.resource:
        resource_path = Path(args.resource)
        if not resource_path.is_file():
            return setup_failure(f"resource file not found: {resource_path}", args.monitor_mode)
        resource = load_resource(resource_path)
    elif args.raw_http:
        raw_path = Path(args.raw_http)
        if not raw_path.is_file():
            return setup_failure(f"raw HTTP file not found: {raw_path}", args.monitor_mode)
        resource = extract_json_body(raw_path.read_text(encoding="utf-8"))
        temp_resource = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with temp_resource:
            json.dump(resource, temp_resource, ensure_ascii=False)
        resource_path = Path(temp_resource.name)
    else:
        return setup_failure("one of --resource or --raw-http is required", args.monitor_mode)

    profile = args.profile or profile_for_resource(resource)
    if args.require_profile and not profile:
        return setup_failure("unable to infer a KR Core profile for resource", args.monitor_mode)

    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "operationoutcome.json"
        command = build_validator_command(
            args.java,
            validator_jar,
            resource_path,
            output_path,
            args.version,
            args.ig,
            profile,
            args.tx,
        )
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
        except FileNotFoundError:
            return setup_failure(f"java executable not found: {args.java}", args.monitor_mode)
        except subprocess.TimeoutExpired:
            return OracleResult(result_class=INCONCLUSIVE_ORACLE, exit_code=0 if args.monitor_mode else 2, detail="validator timeout", validator_command=command)

        outcome = read_outcome(output_path, completed.stdout)
        if completed.returncode != 0 and outcome is None:
            detail_parts = [f"validator_exit_code={completed.returncode}"]
            if completed.stderr.strip():
                detail_parts.append(f"stderr={completed.stderr.strip()}")
            elif completed.stdout.strip():
                detail_parts.append(f"stdout={completed.stdout.strip()}")
            return OracleResult(
                result_class=INCONCLUSIVE_ORACLE,
                exit_code=0 if args.monitor_mode else 2,
                detail="; ".join(detail_parts),
                validator_command=command,
            )

        result = classify_validation(completed.returncode, outcome, args.expected, args.strict_warnings)
        result.validator_command = command
        if completed.stderr.strip():
            result.detail = f"{result.detail}; stderr={completed.stderr.strip()}" if result.detail else completed.stderr.strip()
        return result


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run HL7 FHIR validator_cli.jar as a KR Core oracle wrapper.")
    parser.add_argument("--resource", help="FHIR JSON resource file to validate.")
    parser.add_argument("--raw-http", help="Raw HTTP request file; the JSON body will be extracted and validated.")
    parser.add_argument("--validator-jar", help="Path to validator_cli.jar. Can also be set with FHIR_VALIDATOR_CLI_JAR.")
    parser.add_argument("--java", default="java", help="Java executable path.")
    parser.add_argument("--version", default=FHIR_VERSION, help="FHIR version passed to validator_cli.jar.")
    parser.add_argument("--ig", default=KR_CORE_IG, help="FHIR IG package id or local package .tgz path.")
    parser.add_argument("--profile", help="Canonical profile URL. If omitted, inferred from resourceType/code.")
    parser.add_argument("--tx", default="n/a", help="Terminology server setting. Default n/a avoids external terminology calls.")
    parser.add_argument("--expected", choices=["valid", "invalid", "any"], default="valid", help="Expected validation class.")
    parser.add_argument("--require-profile", action="store_true", help="Treat resources without inferred/provided profile as oracle setup failure.")
    parser.add_argument("--strict-warnings", action="store_true", help="Treat warnings as validation failures.")
    parser.add_argument("--monitor-mode", action="store_true", help="Return exit 0 for inconclusive setup failures so they do not become target weaknesses.")
    parser.add_argument("--timeout", type=int, default=60, help="Validator timeout in seconds.")
    parser.add_argument("--json", action="store_true", help="Print normalized JSON result.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    result = validate_resource(args)
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"{result.result_class}: {result.detail}".strip())
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
