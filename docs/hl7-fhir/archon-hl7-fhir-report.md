# Archon HL7/FHIR 적용 리포트

조사일: 2026-06-05

## 목적

Archon 자체에 신규 프로토콜로 HL7 계열을 추가할 때, FHIR를 1차 MVP로 삼아 Sandbag target server를 구현하고 PIT fuzzing에 필요한 표면을 정리하는 것이 목적입니다.

## 레포지토리 역할

| 레포 | 역할 |
|---|---|
| `Archon` | 실제 fuzzing 엔진/API. protocol package, PIT 생성, publisher/monitor, execution 담당 |
| `ArchonZ` | Theia/Electron 기반 UI/IDE. `archon.exe api --port 5001`에 붙어 protocol/profile/run 설정 |
| `ArchonZ-Sandbag` | Archon이 공격/연결 테스트할 외부 target server/simulator 모음 |

이번 구현은 `ArchonZ-Sandbag`에 FHIR server target을 추가한 것입니다. Archon 본체에 FHIR protocol package를 추가하는 작업은 다음 단계입니다.

## Sandbag 설계

FHIR Sandbag은 “가짜 병원 또는 EMR FHIR 서버”입니다.

| 항목 | 값 |
|---|---|
| 표준 기준 | FHIR R4 4.0.1 |
| Transport | HTTP, 향후 HTTPS 가능 |
| Format | `application/fhir+json` |
| Base path | `/fhir` |
| 구현 파일 | `services/fhir_service.py` |
| 검증 파일 | `test_fhir_verify.py` |
| main 연동 | `python main.py --fhir_only ...` 또는 전체 서비스와 함께 `--fhir_on` |
| seed resource | `Patient/example`, `Observation/example` |

FHIR 서버는 `ThreadingHTTPServer` 기반으로 구현했습니다. FastAPI나 외부 FHIR 라이브러리를 쓰지 않은 이유는 Sandbag이 fuzzing target이므로 가볍고 dependency 충돌이 적고, malformed request에도 예측 가능하게 반응하는 것이 우선이기 때문입니다.

## 구현된 FHIR 기능

- `GET /fhir/__health`
- `GET /fhir/metadata`
- `GET /fhir/Patient/{id}`
- `GET /fhir/Observation/{id}`
- `GET /fhir/Patient?...`
- `GET /fhir/Observation?...`
- `POST /fhir/Patient`
- `POST /fhir/Observation`
- `POST /fhir/Patient/_search`
- `POST /fhir/Observation/_search`
- `PUT /fhir/Patient/{id}`
- `PUT /fhir/Observation/{id}`
- `OperationOutcome` 오류 응답

## Archon 쪽에 신규 프로토콜로 넣는 방법

서브에이전트와 로컬 구조 확인 기준으로, Archon의 신규 프로토콜 최소 진입점은 다음입니다.

```text
C:\Users\vip\suresoft\Archon\prebuilt\attacks\ethernet\fhir\
  meta.json
  params.json
  spec.acz
```

FHIR는 HTTP REST 계열이므로 1차 위치는 `prebuilt\attacks\ethernet\fhir`가 자연스럽습니다. `healthcare\fhir` 같은 새 분류도 가능하지만, 현재 Archon의 HTTP/HTTPS 예제가 ethernet 아래에 있으므로 UI와 기존 link layer 흐름을 덜 건드립니다.

예상 metadata:

```json
{
  "Name": "FHIR",
  "DisplayName": "HL7 FHIR R4",
  "LinkLayer": "TCP",
  "Support": true
}
```

`params.json`에는 최소 다음 항목이 필요합니다.

| 파라미터 | 예시 | 용도 |
|---|---|---|
| `Host` | `127.0.0.1` | Sandbag host |
| `Port` | `8080` | Sandbag port |
| `BasePath` | `/fhir` | FHIR base path |
| `ResourceType` | `Patient` | PIT target resource |
| `ResourceId` | `example` | read/update 대상 |
| `Timeout` | `3000` | publisher/monitor timeout |

초기에는 전용 `FhirPublisher` 없이 기존 TCP/HTTP PIT template으로도 갈 수 있습니다. 다만 JSON body를 구조적으로 mutate하고 HTTP status/FHIR OperationOutcome을 더 잘 해석하려면 이후 전용 `FhirPublisher` 또는 FHIR-aware monitor를 추가하는 것이 좋습니다.

## ArchonZ UI 고려 사항

ArchonZ는 자체적으로 protocol 목록을 하드코딩하지 않고 Archon API의 `/Protocol/protocols` 응답을 받아 UI에 보여줍니다. 따라서 Archon의 `prebuilt\attacks`에 FHIR meta가 들어가고 API가 인식하면 UI에도 프로토콜 카드가 뜨는 구조입니다.

다만 새 `LinkLayer` 값을 만들면 UI 아이콘/렌더링이 비어 보일 수 있습니다. 그래서 MVP에서는 새 link layer를 만들지 않고 `TCP` 또는 HTTPS가 필요한 경우 `TLS/SSL` 계열을 쓰는 것이 안전합니다.

## PIT fuzzing 표면

FHIR는 HTTP 기반이므로 fuzzing 표면은 크게 5개입니다.

공식 표준 근거와 Archon/PIT 추론을 분리한 상세 검수는 [pit-fuzzing-source-audit.md](pit-fuzzing-source-audit.md)를 참고합니다. 아래 표에서 `Content-Length`, server liveness, timeout은 FHIR 표준 자체의 resource interaction이 아니라 HTTP/Archon oracle 관점의 fuzzing 표면입니다.

| 표면 | 예시 |
|---|---|
| Request line | method, path, resource type, id, `_search`, trailing slash |
| Query | `name`, `identifier`, `code`, `subject`, `_format`, repeated param |
| Header | `Accept`, `Content-Type`, `Content-Length`, `If-Match`, `Prefer` |
| JSON body | `resourceType`, `id`, `meta`, `identifier`, `name`, `code`, `subject`, `valueQuantity` |
| Response oracle | status code, content-type, OperationOutcome, server liveness |

초기 PIT seed는 다음 시나리오가 좋습니다.

1. `GET /fhir/metadata`
2. `GET /fhir/Patient/example`
3. `GET /fhir/Patient?name=Kim`
4. `POST /fhir/Patient` with small JSON body
5. `PUT /fhir/Observation/example` with JSON body
6. `POST /fhir/Patient/_search` with form body
7. invalid content type / invalid JSON / unsupported `_format`

실제 Archon PIT test 이름으로 내리면 1차는 아래처럼 잡는 것이 좋습니다.

| 우선순위 | Test name 후보 | Mutate 대상 | 기대 oracle |
|---|---|---|---|
| 1 | `FhirMetadataFormatTest` | `_format`, `Accept` | 200 `CapabilityStatement` 또는 406 `OperationOutcome` |
| 1 | `FhirPatientReadIdTest` | path id | 200 `Patient`, 404/400 `OperationOutcome` |
| 1 | `FhirPatientSearchIdentifierTokenTest` | `identifier=system|value` | 200 `Bundle` |
| 1 | `FhirPatientCreateIdentifierTest` | `resourceType`, `id`, `identifier`, `name` | 201 `Patient` 또는 400/422 `OperationOutcome` |
| 1 | `FhirObservationCreateCodeTest` | `status`, `code`, `subject`, `valueQuantity` | 201 `Observation` 또는 400/422 `OperationOutcome` |
| 2 | `FhirInvalidJsonTest` | malformed JSON body | 400 `OperationOutcome`, no crash |
| 2 | `FhirUnsupportedMediaTypeTest` | `Content-Type` | 415 `OperationOutcome` |
| 2 | `FhirUnsupportedFormatTest` | `_format=xml` | 406 `OperationOutcome` |
| 2 | `FhirUnsupportedMethodTest` | unsupported HTTP method | 405 `OperationOutcome` |

## Oracle 설계

MVP 단계에서는 다음을 fault로 볼 수 있습니다.

- Sandbag process crash 또는 timeout.
- `/fhir/__health`가 200을 반환하지 않음.
- 정상 seed 요청에서 2xx가 아닌 상태.
- 오류 요청에서 `OperationOutcome` 없이 connection reset 또는 invalid JSON 응답.
- `Content-Type`이 FHIR JSON 또는 JSON 계열이 아님.

Archon에는 기본 HTTP monitor를 붙여 health URL을 확인하고, 다음 단계에서 PythonScriptResultMonitor로 FHIR-specific invariant 검사 스크립트를 붙이는 구성이 현실적입니다. 단, `/fhir/__health`는 공식 FHIR endpoint가 아니라 Sandbag 안정성 확인용 편의 endpoint입니다.

## 고객 요구사항 확인 질문

FHIR를 계속 가도 되는지 확정하려면 고객사에 아래를 확인해야 합니다.

| 질문 | 의미 |
|---|---|
| “HL7 v2.x MLLP인가요, FHIR REST API인가요?” | 가장 중요한 분기 |
| “메시지 예시가 `MSH|PID|OBX` 형태인가요, JSON resource인가요?” | v2/FHIR 구분 |
| “endpoint가 `https://.../fhir/Patient` 형태인가요?” | FHIR 가능성 |
| “사용 FHIR version은 R4, R4B, R5 중 무엇인가요?” | spec/package 선택 |
| “필요 resource는 Patient/Observation 외 무엇인가요?” | MVP 확장 범위 |
| “인증은 SMART/OAuth/JWT/mTLS/API key 중 무엇인가요?” | production-like sandbag 확장 |
| “FHIR profile/IG가 있나요?” | validation oracle 구성 |

## 지금 구현된 MVP가 충분한 범위

이번 MVP는 “Archon에 HL7 FHIR를 새 protocol로 넣을 수 있는지”를 검증하기 위한 target server로는 충분합니다.

- 서버가 뜹니다.
- `/metadata`가 있습니다.
- 기본 resource CRUD/search가 있습니다.
- JSON body fuzzing 표면이 있습니다.
- header/content-type/status-code 오류 oracle이 있습니다.
- malformed input에서 서버가 바로 죽지 않고 `OperationOutcome`을 반환합니다.

하지만 “고객사 HL7 연동 전체 대응”으로는 아직 부족합니다. 고객이 HL7 v2 MLLP를 요구하면 별도 TCP/MLLP Sandbag을 만들어야 하고, FHIR production 시나리오라면 auth/TLS/profile validation/terminology/resource 확장이 필요합니다.

## 다음 개발 제안

1. `Archon\prebuilt\attacks\ethernet\fhir`에 `meta.json`, `params.json`, `spec.acz` 추가.
2. 기존 HTTP `spec.acz`를 참고해 FHIR request/response StateModel 구성.
3. `Patient`, `Observation`, `Bundle`, `OperationOutcome` JSON body를 PIT DataModel로 분리.
4. `HttpResponseMonitor`로 `/fhir/__health` 확인.
5. Python oracle script로 FHIR 응답 invariant 확인.
6. 고객 요구가 v2이면 `HL7 v2 MLLP Sandbag`을 별도 구현.
