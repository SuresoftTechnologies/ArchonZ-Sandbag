# FHIR PIT Fuzzing Source Audit

검수일: 2026-06-05

## 결론

`archon-hl7-fhir-report.md`의 큰 방향은 맞습니다. FHIR는 공식 R4 표준 기준으로 HTTP/HTTPS REST API이고, `CapabilityStatement`, resource read/create/update/search, JSON MIME type, `_format`, form-encoded `_search`, `OperationOutcome` 오류 응답은 공식 문서에 근거가 있습니다.

다만 일부 항목은 “공식 FHIR 표준이 직접 지시한 fuzz target”이 아니라 “FHIR가 HTTP 위에서 동작하기 때문에 Archon/PIT 관점에서 잡은 fuzz surface”입니다. 아래처럼 출처 등급을 나눠야 합니다.

| 항목 | 판정 | 이유 |
|---|---|---|
| `GET /metadata` | 표준 직접 근거 있음 | REST API가 CapabilityStatement 제공을 요구 |
| `GET /Patient/{id}` | 표준 직접 근거 있음 | read interaction |
| `POST /Patient`, `PUT /Observation/{id}` | 표준 직접 근거 있음 | create/update interaction |
| `GET /Patient?name=...`, `GET /Observation?code=...` | 표준 직접 근거 있음 | search interaction + resource search parameters |
| `POST /Patient/_search` with form body | 표준 직접 근거 있음 | POST search and `application/x-www-form-urlencoded` |
| `Accept`, `Content-Type`, `_format` | 표준 직접 근거 있음 | FHIR MIME/content negotiation rules |
| `OperationOutcome` as error oracle | 표준 근거 있음, MVP에서는 의도적으로 더 엄격하게 사용 | FHIR는 4xx/5xx에서 OperationOutcome 사용을 정의하지만 모든 generic error에 반드시 요구하지는 않음 |
| `Content-Length` mutation | HTTP 계층 근거, FHIR 직접 근거 아님 | raw TCP HTTP fuzzing surface |
| server liveness, timeout | Archon oracle 추론 | 표준 기능이 아니라 fuzzing 판단 기준 |
| `/fhir/__health` | Sandbag 편의 endpoint | 공식 FHIR endpoint 아님 |
| `If-Match`, `Prefer` | 표준 근거는 있으나 현재 MVP 1차 fuzz 대상 아님 | 현재 CapabilityStatement에 versioned-update/Prefer 동작을 광고하지 않음 |

## DIN/ISO와 비교한 결론

Archon의 기존 DIN/ISO 패키지는 메시지 세션 단위 fuzzing입니다.

| 항목 | DIN SPEC 70121 / ISO 15118-2 | HL7 FHIR MVP |
|---|---|---|
| 기존 Archon 위치 | `prebuilt\attacks\automotive_ethernet\din spec 70121`, `iso 15118-2` | 권장: `prebuilt\attacks\ethernet\fhir` |
| Target role | SECC target | FHIR server target |
| Archon role | EVCC-side session driver | FHIR HTTP client/fuzzer |
| Transport | ISO: SDP, V2GTP, TLS/TCP/IPv6, EXI. DIN: SDP, V2GTP, plain TCP, EXI | HTTP over TCP, optional HTTPS |
| Publisher | 전용 `Iso15118Secc`, `Din70121` publisher | MVP는 TCP/HTTP template 가능. 이후 `FhirPublisher` 권장 |
| Mutation unit | 세션 메시지의 특정 필드. 예: SessionSetupReq.EVCCID, ChargeParameterDiscoveryReq 값 | HTTP interaction, query, header, JSON resource field |
| Oracle | 세션 진행, 응답 메시지, timeout, Soft/Fault exception | HTTP status, FHIR resourceType, OperationOutcome, Bundle, liveness |

이 비교 때문에 FHIR에서 DIN/ISO처럼 `SessionSetupReq`, `CableCheckReq` 같은 흐름을 만들면 안 됩니다. FHIR는 공식 표준상 RESTful resource manager 구조이므로, fuzzing은 HTTP request/response와 resource JSON 구조를 중심으로 잡아야 합니다.

## 공식 표준 근거 체크

| Fuzzing 항목 | 공식 근거 | 적용 |
|---|---|---|
| RESTful FHIR API | https://hl7.org/fhir/R4/http.html | FHIR protocol family를 HTTP/HTTPS REST로 둠 |
| 서버 CapabilityStatement | https://hl7.org/fhir/R4/http.html, https://hl7.org/fhir/R4/capabilitystatement.html | `/metadata`를 첫 seed와 capability oracle로 사용 |
| Service base URL | https://hl7.org/fhir/R4/http.html | `[base]/Patient`, `[base]/Observation` path fuzzing |
| read/create/update/search interactions | https://hl7.org/fhir/R4/http.html | 1차 seed interaction 선정 |
| MIME type | https://hl7.org/fhir/R4/http.html, https://hl7.org/fhir/R4/json.html | `application/fhir+json`, `406`, `415` fuzzing |
| `_format` | https://hl7.org/fhir/R4/http.html | `_format=json/xml/invalid` |
| POST `_search` form body | https://hl7.org/fhir/R4/http.html | `POST /Patient/_search` + form body fuzzing |
| Search parameters | https://hl7.org/fhir/R4/search.html, https://hl7.org/fhir/R4/patient.html, https://hl7.org/fhir/R4/observation.html | `name`, `identifier`, `code`, `subject` |
| OperationOutcome | https://hl7.org/fhir/R4/operationoutcome.html | 오류 응답 oracle |
| Patient structure | https://hl7.org/fhir/R4/patient.html | `identifier`, `name`, `gender`, `birthDate`, `active` body fuzzing |
| Observation structure | https://hl7.org/fhir/R4/observation.html | `status`, `code`, `subject`, `valueQuantity` body fuzzing |
| ISO 15118-2 비교 | https://www.iso.org/standard/55366.html | DIN/ISO와 FHIR의 protocol family 차이 설명 |
| DIN/TS 70121 비교 | https://www.dinmedia.de/en/pre-standard/din-ts-70121/379319307 | DIN 계열이 DC EV charging communication 표준임을 확인 |

## 지금 fuzzing으로 무엇을 하면 되는가

1차 목표는 “FHIR server가 표준 HTTP/FHIR 입력 변형을 받았을 때 crash/timeout 없이 올바른 status와 FHIR resource를 반환하는가”입니다.

### 1순위: 정상 seed 기반 구조 fuzzing

| Test name 후보 | Request | Mutate할 필드 | 기대 oracle |
|---|---|---|---|
| `FhirMetadataFormatTest` | `GET /fhir/metadata?_format=json` | `_format`, `Accept` | 200 `CapabilityStatement` 또는 406 `OperationOutcome` |
| `FhirPatientReadIdTest` | `GET /fhir/Patient/example` | path id | 200 `Patient`, 404/400 `OperationOutcome` |
| `FhirPatientSearchNameTest` | `GET /fhir/Patient?name=Kim` | `name` query value, repeated params | 200 `Bundle` |
| `FhirPatientSearchIdentifierTokenTest` | `GET /fhir/Patient?identifier=system|value` | token `system`, token `value`, separator `|` | 200 `Bundle` |
| `FhirPatientCreateIdentifierTest` | `POST /fhir/Patient` | `resourceType`, `id`, `identifier.system`, `identifier.value`, `name.family`, `name.given` | 201 `Patient` or 400/422 `OperationOutcome` |
| `FhirObservationCreateCodeTest` | `POST /fhir/Observation` | `status`, `code.coding.system`, `code.coding.code`, `subject.reference`, `valueQuantity.value/unit/code` | 201 `Observation` or 400/422 `OperationOutcome` |
| `FhirObservationUpdateTest` | `PUT /fhir/Observation/example` | URL id, body id, status, code, valueQuantity | 200 `Observation` or 400/422 `OperationOutcome` |
| `FhirPostSearchFormTest` | `POST /fhir/Patient/_search` | form body params, query+body repeated params | 200 `Bundle`, 415 for wrong content type |

### 2순위: 오류/negative oracle fuzzing

| Test name 후보 | Request | Mutate할 필드 | 기대 oracle |
|---|---|---|---|
| `FhirUnsupportedMediaTypeTest` | `POST /fhir/Patient` | `Content-Type` | 415 `OperationOutcome` |
| `FhirInvalidJsonTest` | `POST /fhir/Patient` | malformed JSON, truncated body | 400 `OperationOutcome`, no crash |
| `FhirUnsupportedFormatTest` | `GET /fhir/Patient/example?_format=xml` | `_format` | 406 `OperationOutcome` because MVP only supports JSON |
| `FhirUnsupportedMethodTest` | `PATCH /fhir/Patient/example` | HTTP method | 405 `OperationOutcome` |
| `FhirBasePathBoundaryTest` | `GET /fhirPatient` | path boundary | 404 `OperationOutcome` |
| `FhirIdValidationTest` | `POST /fhir/Patient` | invalid `id`, slash in id, overlong id | 400 `OperationOutcome` |

### 3순위: 현재 MVP 밖이지만 다음에 넣을 수 있는 fuzzing

| 항목 | 왜 보류 |
|---|---|
| `If-Match` version-aware update | CapabilityStatement에 versioning support를 아직 명시하지 않음 |
| `Prefer: return=minimal/representation/OperationOutcome` | 표준 근거는 있으나 MVP가 아직 처리하지 않음 |
| `PATCH` | CapabilityStatement에 patch를 광고하지 않음 |
| `DELETE`, history, transaction/batch | MVP 범위 밖 |
| XML/RDF | MVP는 JSON만 광고 |
| SMART/OAuth/TLS | 고객 요구 확인 후 production-like 단계에서 추가 |

## 실제 seed 검증 결과

실행 중인 Sandbag 서버 `http://127.0.0.1:8080/fhir`에 대해 1차 seed 후보를 직접 검증했습니다.

| Seed | 결과 |
|---|---|
| health oracle | PASS, 200 |
| capabilities metadata | PASS, 200 `CapabilityStatement` |
| read `Patient/example` | PASS, 200 `Patient` |
| search Patient by name | PASS, 200 `Bundle` |
| create Patient JSON | PASS, 201 `Patient` |
| create Observation JSON | PASS, 201 `Observation` |
| update Observation JSON | PASS, 200 `Observation` |
| POST Patient `_search` form | PASS, 200 `Bundle` |
| invalid content type | PASS, 415 `OperationOutcome` |
| invalid JSON | PASS, 400 `OperationOutcome` |
| unsupported `_format=xml` | PASS, 406 `OperationOutcome` |
| unsupported method PATCH | PASS, 405 `OperationOutcome` |

## 기존 `archon-hl7-fhir-report.md`에 대한 검수 의견

수정 없이 유지해도 되는 내용:

- FHIR를 HTTP/HTTPS REST 계열로 분류한 것.
- Sandbag을 FHIR server, Archon을 FHIR client/fuzzer로 둔 것.
- `prebuilt\attacks\ethernet\fhir`를 1차 위치로 제안한 것.
- `Patient`, `Observation`, `Bundle`, `OperationOutcome` 중심으로 잡은 것.
- `/fhir/__health`를 Archon health oracle로 쓰자는 제안.

보강해야 하는 내용:

- `Content-Length`, server liveness, timeout은 공식 FHIR 표준 항목이 아니라 HTTP/Archon oracle 추론이라고 명시해야 합니다.
- `If-Match`, `Prefer`는 표준 근거가 있지만 현재 MVP 1차 fuzzing에서는 보류해야 합니다.
- FHIR-specific PIT seed는 추상적인 “JSON body”보다 `Patient.identifier`, `Patient.name`, `Observation.status`, `Observation.code`, `Observation.subject`, `Observation.valueQuantity`처럼 resource field 단위로 작성해야 합니다.
- Oracle은 “무조건 모든 오류가 OperationOutcome이어야 한다”가 아니라, MVP에서는 fuzzing 안정성을 위해 그렇게 강제한다고 표현하는 편이 더 정확합니다.
