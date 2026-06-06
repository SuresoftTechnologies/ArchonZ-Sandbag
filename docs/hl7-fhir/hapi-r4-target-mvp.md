# HAPI FHIR R4 Target MVP

이 문서는 1차 Sandbag FHIR MVP 이후, Archon FHIR package를 실제성 있는 로컬 HAPI FHIR R4 backend에 붙이는 2차 MVP 확정안입니다.

## 1. 결론

2차 MVP의 타겟은 `SMART-EHR-Launcher`가 아니라 로컬 HAPI FHIR R4 server입니다.

```text
Archon FHIR package -> http://127.0.0.1:8090/fhir -> Local HAPI FHIR R4
```

`SMART-EHR-Launcher`와 `smart-launcher-v2` proxy는 3차에서 다룹니다. 2차에서는 OAuth, browser CORS, SMART launch context 변수를 제거하고, 순수 FHIR R4 backend 호환성만 확인합니다.

## 2. 2차 MVP에서 확정한 값

| 항목 | 값 | 비고 |
|---|---|---|
| Target | Local HAPI FHIR R4 | 공개 HAPI 서버는 fuzzing 금지 |
| FHIR version | `4.0.1` | `/metadata`의 `fhirVersion`으로 확인 |
| Host | `127.0.0.1` | same-host local run |
| Port | `8090` | HAPI container의 host port |
| BasePath | `/fhir` | HAPI local server base path |
| ConnectionTestPath | `/metadata` | FHIR REST capabilities interaction |
| HealthPath | `/metadata` | HAPI에는 Sandbag 전용 `/__health`가 없음 |
| Accept | `application/fhir+json` | FHIR JSON media type |
| ContentType | `application/fhir+json` | Create request body |
| Timeout | `10000` | HAPI startup/metadata 응답 지연을 고려한 2차 권장값 |
| Interface | `Default` | OS routing / loopback |

## 3. HAPI 실행

Docker가 있는 환경에서는 HAPI JPA server starter image를 로컬에 띄웁니다. HAPI image의 container port는 `8080`이고, 2차 MVP에서는 1차 Sandbag의 `8080`과 충돌하지 않도록 host port를 `8090`으로 매핑합니다.

```powershell
docker run --rm --name hapi-r4 -p 8090:8080 hapiproject/hapi:latest
```

공식 quick-start처럼 `-p 8080:8080`을 써도 되지만, 그 경우 Archon `Port`와 Wireshark filter를 모두 `8080`으로 바꿔야 합니다.

서버가 뜬 뒤 아래를 먼저 확인합니다.

```powershell
Invoke-RestMethod -Headers @{Accept="application/fhir+json"} http://127.0.0.1:8090/fhir/metadata
```

Pass 기준:

```text
resourceType = CapabilityStatement
fhirVersion  = 4.0.1
```

만약 `fhirVersion`이 R4가 아니면 해당 HAPI image/config가 2차 MVP 기준과 맞지 않습니다. 이 경우 HAPI starter 설정에서 `hapi.fhir.fhir_version: R4`를 명시한 뒤 다시 확인합니다.

## 4. Swagger / OpenAPI 확인

HAPI OpenAPI interceptor가 켜진 서버에서는 다음 endpoint가 열립니다.

```text
http://127.0.0.1:8090/fhir/api-docs
http://127.0.0.1:8090/fhir/swagger-ui/
```

PowerShell 확인:

```powershell
Invoke-RestMethod http://127.0.0.1:8090/fhir/api-docs
Start-Process http://127.0.0.1:8090/fhir/swagger-ui/
```

Swagger는 fuzzing 대상이 아니라 target surface 확인용입니다. Archon이 실제로 fuzzing하는 endpoint는 `/metadata`, `/Patient`, `/Observation` 같은 FHIR REST endpoint입니다. HAPI 환경에 따라 `/api-docs`는 JSON이 아니라 `text/yaml` OpenAPI로 반환될 수 있습니다.

## 5. Archon UI 설정

NIC setting:

| Field | Value |
|---|---|
| Host | `127.0.0.1` |
| Port | `8090` |
| Interface | `Default` |
| Url | `/` |
| RetryMode | `FirstAndAfterFault` |
| FaultOnConnectionFailure | `True` |
| Lifetime | `Iteration` |
| Timeout | `10000` |
| SendTimeout | `5000` |
| ConnectTimeout | `10000` |

FHIR params:

| Field | Sandbag 1차 | HAPI 2차 |
|---|---|---|
| BasePath | `/fhir` | `/fhir` |
| ConnectionTestPath | `/metadata` | `/metadata` |
| HealthPath | `/__health` | `/metadata` |
| ResourceType | `Patient` | `Patient` |
| ResourceId | `example` | `example` |
| Accept | `application/fhir+json` | `application/fhir+json` |
| ContentType | `application/fhir+json` | `application/fhir+json` |
| Timeout | `3000` | `10000` |

HAPI에서 `Patient/example`이 없을 수 있으므로, `FhirPatientReadIdTest`는 404/OperationOutcome을 정상적인 서버 응답으로 볼 수 있습니다. ConnectionTest는 `/metadata`로 판단합니다.

## 6. Monitor 설정

Sandbag:

```text
http://127.0.0.1:8080/fhir/__health
```

HAPI:

```text
http://127.0.0.1:8090/fhir/metadata
```

Archon FHIR package의 monitor URL은 아래 템플릿입니다.

```xml
http://##Host##:##Port####BasePath####HealthPath##
```

따라서 HAPI 2차 MVP에서는 `HealthPath=/metadata`로 설정합니다. HAPI metadata response가 느리거나 server가 warm-up 중이면 3000ms monitor timeout이 false fault를 만들 수 있으므로 `Timeout=10000`을 우선 사용합니다.

## 7. Target verifier

외부 FHIR endpoint 검증은 Sandbag을 자동 실행하지 않는 별도 스크립트를 사용합니다.

Read-only smoke:

```powershell
python test_fhir_target_verify.py --base-url http://127.0.0.1:8090/fhir
```

로컬 HAPI 쓰기 roundtrip까지 확인:

```powershell
python test_fhir_target_verify.py --base-url http://127.0.0.1:8090/fhir --allow-write
```

`--allow-write`는 기본적으로 localhost 계열 URL에서만 허용됩니다. 사설망의 명시적으로 허가된 non-local target에 쓰기 검증을 해야 할 때만 아래 옵션을 추가합니다.

```powershell
python test_fhir_target_verify.py --base-url http://<private-hapi-host>:8090/fhir --allow-write --allow-non-local-write
```

Swagger가 꺼진 HAPI config라면:

```powershell
python test_fhir_target_verify.py --base-url http://127.0.0.1:8090/fhir --allow-write --skip-swagger
```

`--allow-write`는 로컬 또는 명시적으로 허가된 서버에서만 사용합니다. 공개 HAPI 서버에는 쓰기 테스트를 하지 않습니다.

## 8. Wireshark 확인

Adapter:

```text
Npcap Loopback Adapter
```

Display filters:

```text
tcp.port == 8090
tcp.port == 8090 && http
tcp.port == 8090 && http.request.uri contains "/fhir/metadata"
tcp.port == 8090 && frame contains "Accept:"
```

`FhirMetadataFormatTest` 확인 시 TCP stream에서 아래 형태가 보여야 합니다.

```http
GET /fhir/metadata?_format=<mutated-value> HTTP/1.1
Host: 127.0.0.1:8090
Accept: <mutated-value>
Connection: close
```

공식 HAPI public demo처럼 HTTPS endpoint를 직접 보려는 경우에는 현재 raw `Tcp` publisher로는 payload fuzzing 대상이 되지 않습니다. 2차 MVP는 plain HTTP local HAPI만 대상으로 합니다.

## 9. Pass / fail 기준

| Check | Pass condition |
|---|---|
| HAPI metadata | `GET /fhir/metadata`가 200 `CapabilityStatement` 반환 |
| FHIR version | `fhirVersion`이 `4.0.1` |
| Swagger/OpenAPI | `/fhir/api-docs`, `/fhir/swagger-ui/` 접근 가능, 또는 config상 비활성임을 기록 |
| External verifier read-only | metadata + Patient/Observation search pass |
| External verifier write | local HAPI에서 `--allow-write` roundtrip pass |
| Archon connection test | `GET /fhir/metadata` pass |
| Archon fuzzing | 기존 6개 FHIR test가 HAPI endpoint로 송신됨 |
| Packet capture | Wireshark `tcp.port == 8090`에서 mutated field 확인 |

## 10. 2차 MVP에서 하지 않는 것

- SMART-EHR-Launcher 직접 연동.
- `smart-launcher-v2` proxy.
- OAuth/Bearer token.
- HTTPS/TLS.
- XML/RDF.
- batch/transaction/history.
- full profile/terminology validation.
- 전체 FHIR resource 확장.

## 11. 현재 workspace 검증 결과

현재 Windows workspace에서는 `docker` 명령이 PATH에 없어 로컬 HAPI container 실행은 아직 못 했습니다. 대신 공개 HAPI R4 demo에 대해 read-only smoke와 Swagger UI 확인만 수행했습니다.

```powershell
python -m py_compile test_fhir_target_verify.py test_fhir_verify.py services\fhir_service.py
python test_fhir_target_verify.py --base-url https://hapi.fhir.org/baseR4
```

검증 결과:

| Check | Result |
|---|---|
| Python syntax | PASS |
| Public HAPI metadata | PASS, `CapabilityStatement`, `fhirVersion=4.0.1` |
| Public HAPI Patient/Observation read-only search | PASS |
| Public HAPI `/api-docs` | PASS, `text/yaml`, OpenAPI `3.0.1` |
| Public HAPI `/swagger-ui/` | PASS, browser snapshot showed Patient/Observation resources and `/metadata` operation |
| Public HAPI write roundtrip | SKIP, public target이므로 `--allow-write` 미사용 |
| Public write safety guard | PASS, `--allow-write` on non-local target is refused unless `--allow-non-local-write` is also provided |
| Optimized Python safety check | PASS, `python -O` still fails R5 target because verifier uses explicit checks instead of `assert` |
| Local HAPI Docker run | BLOCKED, `docker` command unavailable in current PATH |

Browser evidence:

```text
docs/hl7-fhir/hapi-r4-swagger-ui.png
```

## 12. 근거

- HAPI FHIR OpenAPI 문서는 `OpenApiInterceptor`를 통해 `/api-docs`, `/swagger-ui/`를 제공할 수 있다고 설명합니다.
- HAPI JPA Server starter는 HAPI FHIR JPA server를 시작하기 위한 권장 starter project입니다.
- HAPI Docker image 문서는 `hapiproject/hapi:latest`와 `fhir_version: R4` 설정 예시를 제공합니다.
- FHIR R4 REST API의 capabilities interaction은 `GET [base]/metadata`입니다.
