import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_fhir_validator_cli as oracle


class FhirValidatorCliWrapperTests(unittest.TestCase):
    def test_profile_for_kr_patient(self):
        resource = {
            "resourceType": "Patient",
            "meta": {"profile": [oracle.PATIENT_PROFILE]},
        }

        self.assertEqual(oracle.profile_for_resource(resource), oracle.PATIENT_PROFILE)

    def test_profile_for_body_temperature_observation(self):
        resource = {
            "resourceType": "Observation",
            "meta": {"profile": [oracle.BODY_TEMPERATURE_PROFILE]},
            "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}]},
        }

        self.assertEqual(oracle.profile_for_resource(resource), oracle.BODY_TEMPERATURE_PROFILE)

    def test_extract_json_body_from_raw_http(self):
        raw = (
            "POST /fhir/Patient HTTP/1.1\r\n"
            "Host: 127.0.0.1:8090\r\n"
            "Content-Type: application/fhir+json\r\n\r\n"
            "{\"resourceType\":\"Patient\"}"
        )

        self.assertEqual(oracle.extract_json_body(raw), {"resourceType": "Patient"})

    def test_warning_only_operation_outcome_is_pass_by_default(self):
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "warning", "diagnostics": "example warning"}],
        }

        result = oracle.classify_validation(0, outcome, expected="valid", strict_warnings=False)

        self.assertEqual(result.result_class, oracle.VALID_PROFILE_PASS)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.warnings, 1)

    def test_error_operation_outcome_is_profile_error_for_expected_valid(self):
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "profile violation"}],
        }

        result = oracle.classify_validation(1, outcome, expected="valid", strict_warnings=False)

        self.assertEqual(result.result_class, oracle.PROFILE_ERROR)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.errors, 1)

    def test_error_operation_outcome_can_be_expected_invalid(self):
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "profile violation"}],
        }

        result = oracle.classify_validation(1, outcome, expected="invalid", strict_warnings=False)

        self.assertEqual(result.result_class, oracle.EXPECTED_INVALID)
        self.assertEqual(result.exit_code, 0)

    def test_build_validator_command_includes_ig_and_profile(self):
        command = oracle.build_validator_command(
            "java",
            Path("C:/tools/fhir/validator_cli.jar"),
            Path("patient.json"),
            Path("out.json"),
            "4.0.1",
            "hl7.fhir.kr.core#2.0.0",
            oracle.PATIENT_PROFILE,
            "n/a",
        )

        self.assertIn("-ig", command)
        self.assertIn("hl7.fhir.kr.core#2.0.0", command)
        self.assertIn("-profile", command)
        self.assertIn(oracle.PATIENT_PROFILE, command)
        self.assertIn("-tx", command)
        self.assertIn("n/a", command)

    def test_missing_validator_jar_is_inconclusive_in_monitor_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            resource_path = Path(temp_dir) / "patient.json"
            resource_path.write_text(json.dumps({"resourceType": "Patient"}), encoding="utf-8")
            args = SimpleNamespace(
                resource=str(resource_path),
                raw_http=None,
                validator_jar=str(Path(temp_dir) / "missing-validator.jar"),
                java="java",
                version="4.0.1",
                ig="hl7.fhir.kr.core#2.0.0",
                profile=None,
                tx="n/a",
                expected="valid",
                require_profile=False,
                strict_warnings=False,
                monitor_mode=True,
                timeout=1,
            )

            result = oracle.validate_resource(args)

        self.assertEqual(result.result_class, oracle.INCONCLUSIVE_ORACLE)
        self.assertEqual(result.exit_code, 0)

    def test_validator_nonzero_without_operation_outcome_is_inconclusive(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            validator_path = Path(temp_dir) / "validator_cli.jar"
            validator_path.write_text("placeholder", encoding="utf-8")
            resource_path = Path(temp_dir) / "patient.json"
            resource_path.write_text(json.dumps({"resourceType": "Patient"}), encoding="utf-8")
            args = SimpleNamespace(
                resource=str(resource_path),
                raw_http=None,
                validator_jar=str(validator_path),
                java="java",
                version="4.0.1",
                ig="hl7.fhir.kr.core#2.0.0",
                profile=None,
                tx="n/a",
                expected="invalid",
                require_profile=False,
                strict_warnings=False,
                monitor_mode=False,
                timeout=1,
            )

            with patch("test_fhir_validator_cli.subprocess.run") as run:
                run.return_value = SimpleNamespace(returncode=1, stdout="", stderr="package download failed")
                result = oracle.validate_resource(args)

        self.assertEqual(result.result_class, oracle.INCONCLUSIVE_ORACLE)
        self.assertEqual(result.exit_code, 2)
        self.assertIn("package download failed", result.detail)

    def test_validator_stderr_is_retained_when_operation_outcome_exists(self):
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "profile violation"}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            validator_path = Path(temp_dir) / "validator_cli.jar"
            validator_path.write_text("placeholder", encoding="utf-8")
            resource_path = Path(temp_dir) / "patient.json"
            resource_path.write_text(json.dumps({"resourceType": "Patient"}), encoding="utf-8")
            args = SimpleNamespace(
                resource=str(resource_path),
                raw_http=None,
                validator_jar=str(validator_path),
                java="java",
                version="4.0.1",
                ig="hl7.fhir.kr.core#2.0.0",
                profile=None,
                tx="n/a",
                expected="valid",
                require_profile=False,
                strict_warnings=False,
                monitor_mode=False,
                timeout=1,
            )

            with patch("test_fhir_validator_cli.subprocess.run") as run:
                run.return_value = SimpleNamespace(returncode=1, stdout=json.dumps(outcome), stderr="validator stderr")
                result = oracle.validate_resource(args)

        self.assertEqual(result.result_class, oracle.PROFILE_ERROR)
        self.assertIn("validator stderr", result.detail)


if __name__ == "__main__":
    unittest.main()
