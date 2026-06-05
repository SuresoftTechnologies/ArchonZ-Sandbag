# FHIR Sandbag 서버 사용법

## 역할 비유

기존 ISO 15118 설명을 FHIR로 바꾸면 다음과 같습니다.

```text
ISO 15118:
  Sandbag = SECC, 가짜 충전기 서버
  Archon  = EVCC, 가짜 전기차 클라이언트

FHIR:
  Sandbag = FHIR Server, 가짜 병원/EMR API 서버
  Archon  = FHIR Client/Fuzzer, 가짜 의료 앱 또는 공격/퍼징 클라이언트
```

즉 Sandbag은 환자/검사 데이터를 가진 서버처럼 행동하고, Archon은 그 서버에 HTTP 요청을 보내며 request line, header, query, JSON body를 PIT로 변형합니다.

## 실행

단독 실행이 가장 안정적인 개발 경로입니다.

```powershell
python services\fhir_service.py --host 127.0.0.1 --port 8080 --base-path /fhir
```

`main.py`를 통해 FHIR만 실행하려면 다음 옵션을 사용합니다.

```powershell
python main.py --fhir_only --fhir_host 0.0.0.0 --fhir_port 8080 --fhir_base_path /fhir
```

기존 CAN/SOME-IP/DoIP 서비스와 함께 실행하려면 `--fhir_on`을 사용합니다.

```powershell
python main.py --fhir_on --fhir_host 0.0.0.0 --fhir_port 8080 --fhir_base_path /fhir
```

FHIR 기능만 검증할 때는 단독 실행 또는 `--fhir_only`를 권장합니다. 전체 서비스 실행은 CAN/OBD 등 기존 dependency 상태의 영향을 받을 수 있습니다.

## 기본 URL

```text
http://127.0.0.1:8080/fhir
```

## 지원 endpoint

| Method | Path | 설명 |
|---|---|---|
| `GET` | `/fhir/__health` | Sandbag health check |
| `GET`, `HEAD` | `/fhir/metadata` | FHIR CapabilityStatement |
| `GET` | `/fhir/Patient/{id}` | Patient read |
| `GET` | `/fhir/Observation/{id}` | Observation read |
| `GET` | `/fhir/Patient?name=...&identifier=...` | Patient search |
| `GET` | `/fhir/Observation?code=...&subject=...` | Observation search |
| `POST` | `/fhir/Patient` | Patient create |
| `POST` | `/fhir/Observation` | Observation create |
| `POST` | `/fhir/Patient/_search` | form-encoded Patient search |
| `POST` | `/fhir/Observation/_search` | form-encoded Observation search |
| `PUT` | `/fhir/Patient/{id}` | Patient update |
| `PUT` | `/fhir/Observation/{id}` | Observation update |

지원 resource type은 MVP 기준 `Patient`, `Observation`입니다.

## PowerShell 예시

CapabilityStatement:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/fhir/metadata" `
  -Headers @{ Accept = "application/fhir+json" }
```

Patient 생성:

```powershell
$patient = @{
  resourceType = "Patient"
  name = @(@{ family = "Lee"; given = @("Sora") })
  identifier = @(@{ system = "urn:test"; value = "pit-patient" })
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:8080/fhir/Patient" `
  -ContentType "application/fhir+json" `
  -Headers @{ Accept = "application/fhir+json" } `
  -Body $patient
```

Patient 검색:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/fhir/Patient?name=Lee" `
  -Headers @{ Accept = "application/fhir+json" }
```

`POST _search`:

```powershell
Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:8080/fhir/Patient/_search" `
  -ContentType "application/x-www-form-urlencoded" `
  -Headers @{ Accept = "application/fhir+json" } `
  -Body "identifier=pit-patient"
```

Observation 생성:

```powershell
$observation = @{
  resourceType = "Observation"
  status = "final"
  code = @{
    coding = @(@{ system = "http://loinc.org"; code = "8310-5"; display = "Body temperature" })
    text = "Body temperature"
  }
  subject = @{ reference = "Patient/example" }
  valueQuantity = @{ value = 36.7; unit = "Cel"; system = "http://unitsofmeasure.org"; code = "Cel" }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:8080/fhir/Observation" `
  -ContentType "application/fhir+json" `
  -Headers @{ Accept = "application/fhir+json" } `
  -Body $observation
```

## 오류 응답

MVP는 FHIR `OperationOutcome` 형식으로 오류를 반환합니다.

| 상황 | HTTP status | 응답 |
|---|---:|---|
| 없는 resource read | 404 | `OperationOutcome` |
| 지원하지 않는 `Accept`/`_format` | 406 | `OperationOutcome` |
| 잘못된 `Content-Type` | 415 | `OperationOutcome` |
| JSON syntax 오류 | 400 | `OperationOutcome` |
| URL과 body의 resourceType 불일치 | 422 | `OperationOutcome` |
| batch/transaction Bundle | 400 | `OperationOutcome`, not implemented |

## 검증 스크립트

```powershell
python test_fhir_verify.py
```

검증 항목:

- `/metadata`가 FHIR R4 CapabilityStatement를 반환.
- `Patient` create/read/search가 동작.
- `Observation` create/update/search가 동작.
- 404/415/422/400 오류가 `OperationOutcome`으로 반환.

## MVP 한계

- 실제 병원 데이터가 아닌 synthetic data만 사용합니다.
- persistent database가 없습니다. 서버 재시작 시 seed data로 초기화됩니다.
- JSON만 지원합니다. XML/RDF는 아직 구현하지 않았습니다.
- SMART on FHIR, OAuth, TLS termination, terminology validation, profile validation은 없습니다.
- batch/transaction, patch, delete, history, conditional interaction은 아직 구현하지 않았습니다.
