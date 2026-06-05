# HL7 FHIR Sandbag MVP

이 폴더는 Archon에 신규 프로토콜로 HL7 계열을 넣을 때, 우선 FHIR R4 REST API를 대상으로 분석하고 구현한 자료입니다.

## 한 줄 결론

ISO 15118에서 `Sandbag = SECC`, `Archon = EVCC`였다면, FHIR에서는 다음처럼 보면 됩니다.

| 기준 | Sandbag 역할 | Archon 역할 |
|---|---|---|
| ISO 15118 | 가짜 충전기 서버, SECC | 가짜 전기차 클라이언트, EVCC |
| HL7 FHIR | 가짜 병원/EMR FHIR 서버 | FHIR 클라이언트이자 HTTP/PIT 퍼저 |
| HL7 v2 MLLP | 가짜 병원 인터페이스 엔진 TCP listener | HL7 v2 메시지 송신기/퍼저 |

이번 MVP는 세 번째가 아니라 두 번째입니다. 즉 `HL7 전체` 구현이 아니라 `HL7 FHIR R4 HTTP JSON 서버`를 Sandbag으로 띄운 것입니다.

## 문서

- [standards-summary.md](standards-summary.md): HL7 v2/v3/CDA/FHIR 표준 차이, FHIR 선택 이유, 다운로드한 공식 문서/아티팩트.
- [fhir-sandbag-usage.md](fhir-sandbag-usage.md): 서버 실행법, API 예시, PowerShell 호출 예시, 오류 응답.
- [archon-hl7-fhir-report.md](archon-hl7-fhir-report.md): Archon/ArchonZ/Sandbag 적용 분석, PIT fuzzing 표면, 다음 구현 범위.

## 로컬에 받은 표준 자료

- `raw/R4`: FHIR R4 HTML 표준 문서 일부.
- `raw/R5`: FHIR R5 HTML 표준 문서 일부.
- `raw/v3-cda`: HL7 v3 guide, CDA index HTML.
- `artifacts`: FHIR R4/R5 definitions, examples, schema, NPM package tarball.
- `examples`: R4 JSON examples 중 CapabilityStatement, Patient, Observation, OperationOutcome, Bundle 샘플.

## MVP 서버

구현 파일:

- `services/fhir_service.py`
- `test_fhir_verify.py`
- `main.py`의 `--fhir_on` 옵션

단독 실행:

```powershell
python services\fhir_service.py --host 127.0.0.1 --port 8080 --base-path /fhir
```

`main.py`에서 FHIR만 실행:

```powershell
python main.py --fhir_only --fhir_host 0.0.0.0 --fhir_port 8080 --fhir_base_path /fhir
```

기존 CAN/SOME-IP/DoIP 서비스와 함께 실행:

```powershell
python main.py --fhir_on --fhir_host 0.0.0.0 --fhir_port 8080 --fhir_base_path /fhir
```

검증:

```powershell
python test_fhir_verify.py
```
