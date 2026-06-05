# FHIR Sandbag Live Server Test Report

검증 시각: 2026-06-05 13:31:27 +09:00

## 대상

사용자가 이미 실행한 FHIR Sandbag 서버를 중단하지 않고 외부 요청으로 검증했습니다.

```text
Base URL: http://127.0.0.1:8080/fhir
Command: python .\services\fhir_service.py --host 127.0.0.1 --port 8080 --base-path /fhir
```

## 결론

현재 서버는 정상적으로 떠 있습니다. FHIR R4 CapabilityStatement를 반환하고, MVP 범위인 `Patient`, `Observation` read/create/update/search 및 오류 응답 `OperationOutcome`이 동작했습니다.

## 검증 결과

| 항목 | 결과 |
|---|---|
| Health check | PASS, `/fhir/__health` returned `status=ok` |
| CapabilityStatement | PASS, `/fhir/metadata` returned `resourceType=CapabilityStatement` |
| FHIR version | PASS, `fhirVersion=4.0.1` |
| Format | PASS, `json` advertised |
| Supported resources | PASS, `Patient`, `Observation` |
| Seed Patient read | PASS, `Patient/example` |
| Seed Observation read | PASS, `Observation/example` |
| Patient create/read/search | PASS, created `Patient/codex-live-test`, search total `1` |
| Observation create/update/search | PASS, created `Observation/codex-live-observation`, updated version `2`, search total `2` |
| Missing resource error | PASS, 404 `OperationOutcome` |
| Invalid JSON error | PASS, 400 `OperationOutcome` |
| Unsupported method error | PASS, 405 `OperationOutcome` |

## 생성된 테스트 데이터

서버가 in-memory store를 사용하므로 아래 데이터는 현재 실행 중인 서버 프로세스 안에만 존재합니다. 서버를 재시작하면 사라집니다.

| Resource | ID | 용도 |
|---|---|---|
| `Patient` | `codex-live-test` | create/read/search 검증 |
| `Observation` | `codex-live-observation` | create/update/search 검증 |

## 확인 명령

새 PowerShell 창에서 아래 명령으로 같은 상태를 볼 수 있습니다.

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/fhir/__health" `
  -Headers @{ Accept = "application/fhir+json" }
```

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/fhir/metadata" `
  -Headers @{ Accept = "application/fhir+json" }
```

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/fhir/Patient/codex-live-test" `
  -Headers @{ Accept = "application/fhir+json" }
```

## Archon 연결 관점

Archon에서 이 Sandbag을 target으로 잡을 때의 기본값은 다음과 같습니다.

| 설정 | 값 |
|---|---|
| Protocol family | HTTP |
| FHIR version | R4 4.0.1 |
| Host | `127.0.0.1` |
| Port | `8080` |
| Base path | `/fhir` |
| Health oracle | `GET /fhir/__health` |
| Metadata endpoint | `GET /fhir/metadata` |
| Primary resources | `Patient`, `Observation` |

PIT fuzzing 초반에는 `GET /metadata`, `GET /Patient/example`, `POST /Patient`, `GET /Patient?identifier=...`, `PUT /Observation/{id}`, invalid JSON, bad method, bad content-type를 seed로 쓰면 됩니다.
