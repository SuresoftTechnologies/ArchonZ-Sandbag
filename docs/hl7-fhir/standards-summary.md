# HL7 / FHIR 표준 조사 요약

조사일: 2026-06-05

## 핵심 결론

고객사가 “HL7 프로토콜”이라고만 말하면 바로 FHIR라고 단정하면 안 됩니다. HL7에는 서로 다른 계열이 있습니다.

| 계열 | 실무에서의 의미 | 전송/기술 계열 | Archon Sandbag 방향 |
|---|---|---|---|
| HL7 v2.x | 병원 인터페이스 엔진에서 많이 쓰는 pipe-delimited 메시지. ADT, ORM, ORU 등 | 주로 TCP + MLLP framing. 파일/HTTP 변형도 가능 | 별도 `HL7 v2 MLLP Sandbag` 필요 |
| HL7 v3 | RIM 기반 XML 메시징/모델 계열 | XML, 구현별 transport | MVP 대상 아님. CDA 이해에 중요 |
| CDA | 임상 문서 구조/의미를 정의하는 XML 문서 표준 | 문서 교환. HTTP, repository, message attachment 등 다양 | 문서 parser/fuzzer로 별도 접근 |
| FHIR | Resource 기반 의료 데이터 API 표준 | HTTP/HTTPS REST, JSON/XML/RDF | 이번 MVP 대상 |

따라서 고객사가 “FHIR API” 또는 “FHIR 서버 연동”을 요구한다면 이번 MVP 방향이 맞습니다. 반대로 고객사가 “HL7 v2.5 ADT/ORU over MLLP”, “Mirth/Interface Engine”, “MSH/PID/OBR/OBX 메시지”를 말한다면 FHIR만으로는 요구사항을 충족하지 못합니다.

## FHIR이란 무엇인가

FHIR는 Fast Healthcare Interoperability Resources의 약자이며, 의료 정보를 전자적으로 교환하기 위한 HL7 표준입니다. 공식 R4 overview는 FHIR를 의료 정보 전자 교환 표준으로 설명하고, FHIR가 HL7 v2, HL7 v3/RIM, CDA의 경험을 바탕으로 만들어졌다고 설명합니다.

FHIR의 기본 단위는 `Resource`입니다. `Patient`, `Observation`, `MedicationRequest`, `DiagnosticReport`처럼 의료 업무에서 교환할 수 있는 데이터를 resource로 나누고, 각 resource는 JSON/XML/RDF 등으로 표현됩니다.

FHIR REST API에서는 각 resource type이 collection처럼 동작합니다.

```text
GET  [base]/metadata
GET  [base]/Patient/{id}
GET  [base]/Patient?name=Kim
POST [base]/Patient
PUT  [base]/Patient/{id}
POST [base]/Patient/_search
```

공식 R4 REST API 문서는 FHIR API를 RESTful FHIR라고 부르며, 서버가 지원하는 interaction/resource를 알리는 `CapabilityStatement`를 제공해야 한다고 설명합니다. 같은 문서의 service base URL 형식은 `http{s}://server{/path}`입니다.

## FHIR의 프로토콜 계열

Archon 관점에서 FHIR는 다음처럼 분류하는 것이 가장 자연스럽습니다.

| 항목 | 값 |
|---|---|
| Link layer 후보 | `TCP` 또는 `TLS/SSL` |
| Application protocol | HTTP/HTTPS |
| Message format | JSON 우선, XML/RDF 선택 |
| FHIR MIME type | `application/fhir+json`, `application/fhir+xml`, `application/fhir+turtle` |
| MVP MIME type | `application/fhir+json`만 구현 |
| Discovery endpoint | `GET /fhir/metadata` |
| Error resource | `OperationOutcome` |
| Search response | `Bundle` with `type=searchset` |

공식 R4 REST API 문서는 FHIR resource의 정식 MIME type을 `application/fhir+json`, `application/fhir+xml`, `application/fhir+turtle`로 정리하고, search POST에는 `application/x-www-form-urlencoded`도 쓰인다고 설명합니다. 이번 Sandbag MVP는 이 중 JSON과 form-encoded `_search`만 구현했습니다.

## R4와 R5 중 무엇을 기준으로 할 것인가

R5는 현재 published version이지만 STU입니다. R4는 R4 permanent home이며 mixed Normative/STU이고, REST API, JSON representation, CapabilityStatement, OperationOutcome, Patient 같은 핵심 요소가 normative/ANSI-approved 범위에 들어갑니다.

이번 MVP는 `FHIR R4 4.0.1`을 기준으로 했습니다. 이유는 다음과 같습니다.

- Archon fuzzing target은 안정적인 HTTP/resource 계약이 더 중요합니다.
- R4 core package와 examples/schema가 널리 사용됩니다.
- R5도 같이 다운로드했지만, 첫 프로토콜 패키지는 R4로 시작하는 편이 고객/제품 설명에 안전합니다.
- R4 서버라고 밝히고 `/metadata`의 `fhirVersion`도 `4.0.1`로 반환합니다.

## HL7 v2 설명

HL7 v2는 병원 시스템 사이에서 오래 쓰인 메시징 표준입니다. HL7 UK 설명에 따르면 v2는 환자 행정, admission/discharge/transfer, 회계, 검사 order/report 등 넓은 임상 데이터 교환을 다룹니다. 메시지는 trigger event로 시작되고, segment의 sequence로 구성되며, segment 안 field는 보통 `|`로 구분됩니다.

예시 형태:

```text
MSH|^~\&|LAB|HOSP|EHR|HOSP|202606051030||ORU^R01|MSG0001|P|2.5
PID|1||12345||KIM^MINSOO||19900101|M
OBR|1||ORDER1|8310-5^Body temperature
OBX|1|NM|8310-5^Body temperature||36.7|Cel
```

이 계열을 구현하려면 FHIR 서버가 아니라 TCP listener + MLLP framing + ACK/NAK + segment parser가 필요합니다.

## HL7 v3와 CDA 설명

HL7 v3는 RIM(Reference Information Model)을 바탕으로 일관된 정보 모델과 명확한 conformance를 만들려는 계열입니다. HL7 UK는 v3 표준이 syntax-independent model로 개발되고, 현재 선호 구현 기술은 XML이라고 설명합니다.

CDA는 Clinical Document Architecture이며, 환자 요약과 임상 문서 교환을 위한 문서 markup 표준입니다. 공식 CDA 페이지는 CDA를 clinical documents의 structure와 semantics를 정의하는 document markup standard라고 설명하고, CDA 문서는 human readability 같은 특성을 가집니다.

Archon target으로 CDA를 다룬다면 REST API보다 XML document parser, schema/Schematron, attachment transport, repository endpoint가 fuzzing 표면이 됩니다.

## 이번에 다운로드한 공식 문서/아티팩트

| 구분 | 파일/폴더 | 용도 |
|---|---|---|
| R4 raw HTML | `raw/R4/*.html` | REST API, JSON/XML format, CapabilityStatement, OperationOutcome, Patient, Observation |
| R5 raw HTML | `raw/R5/*.html` | 현재 published version 비교용 |
| v3/CDA raw HTML | `raw/v3-cda/*.html` | HL7 v3/CDA 계열 구분용 |
| R4 definitions | `artifacts/R4-definitions.json.zip` | resource/profile/value set 정의 원본 |
| R4 examples | `artifacts/R4-examples-json.zip` | JSON 예제 원본 |
| R4 schema | `artifacts/R4-fhir.schema.json.zip` | JSON schema 검증 참고 |
| R4 package | `artifacts/hl7.fhir.r4.core.tgz` | FHIR package ecosystem용 core package |
| R5 definitions/examples/schema/package | `artifacts/R5-*`, `hl7.fhir.r5.*.tgz` | R5 비교 및 향후 확장 |
| R4 selected examples | `examples/*.json` | MVP 구현과 문서 예시 기준 |

## 표준 소스

- FHIR R4 overview: https://hl7.org/fhir/R4/overview.html
- FHIR R4 REST API: https://hl7.org/fhir/R4/http.html
- FHIR R4 downloads: https://hl7.org/fhir/R4/downloads.html
- FHIR R4 JSON format: https://hl7.org/fhir/R4/json.html
- FHIR R4 CapabilityStatement: https://hl7.org/fhir/R4/capabilitystatement.html
- FHIR R4 OperationOutcome: https://hl7.org/fhir/R4/operationoutcome.html
- FHIR R4 Patient: https://hl7.org/fhir/R4/patient.html
- FHIR R4 Observation: https://hl7.org/fhir/R4/observation.html
- FHIR R5 downloads/current published version: https://hl7.org/fhir/R5/downloads.html
- HL7 v2 overview: https://www.hl7.org.uk/standards/hl7-standards/hl7-version-2/
- HL7 v3 overview: https://www.hl7.org.uk/standards/hl7-standards/hl7-v3/
- CDA overview: https://hl7.org/cda/
