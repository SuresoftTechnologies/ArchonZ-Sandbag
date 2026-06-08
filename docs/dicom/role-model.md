# DICOM role model

작성일: 2026-06-08

## 한 줄 결론

DICOM에서 Sandbag 또는 Orthanc는 `가짜 PACS/VNA`, 즉 의료영상 저장소 역할을 합니다. Archon은 1차 MVP에서 CT/MRI/X-ray 장비처럼 영상을 보내는 쪽이 되고, 1.5차부터는 viewer 또는 AI client처럼 영상을 검색하고 가져오는 쪽도 됩니다.

## 기존 프로토콜과의 대응

| 프로토콜 | Sandbag/reference target | Archon 역할 | 주고받는 것 |
|---|---|---|---|
| EVCC | 가짜 충전소 | EVCC/차량 쪽 요청자 | 충전 세션 메시지 |
| FHIR | 가짜 병원정보서버 또는 HAPI FHIR server | 의료정보 요청자 | Patient, Observation, Encounter 같은 병원정보 resource |
| DICOM | 가짜 PACS/VNA 또는 Orthanc | 영상 장비, viewer, AI client, DICOM requester | DICOM image/object, study/series/instance metadata |

## DICOM에서 누가 누구인가

```text
CT/MRI/X-ray modality
  -> C-ECHO: PACS 살아있나?
  -> C-STORE: DICOM 영상 저장해라
  -> PACS/VNA
```

ArchonZ-Sandbag MVP에서는 다음처럼 대응합니다.

| 구성요소 | DICOM 세계의 역할 | 설명 |
|---|---|---|
| Archon | DICOM SCU / requester | `C-ECHO`, `C-STORE`, DICOMweb request를 보내는 쪽 |
| Sandbag DICOM target | 가짜 PACS/VNA | 통제 가능한 최소 DICOM server. fuzzing, 실패 oracle, 재현성에 적합 |
| Orthanc | reference mini-PACS | 실제 오픈소스 DICOM server. 정상 동작/호환성 비교 타겟 |
| pydicom | payload factory/oracle | `.dcm` 파일 생성, metadata 파싱, 수신 결과 검증 |
| pynetdicom | DIMSE 구현 라이브러리 | Sandbag 또는 Archon 쪽의 C-ECHO/C-STORE/C-FIND 구현에 사용 |
| DCMTK | 기준 CLI 도구 | `echoscu`, `storescu`, `dcmdump`로 독립 검증 |

## 1차 MVP의 통신 그림

```text
Archon / test client / DCMTK
  -> DICOM DIMSE C-ECHO
  -> DICOM DIMSE C-STORE
  -> Sandbag DICOM target

Archon / test client / DCMTK
  -> DICOM DIMSE C-ECHO
  -> DICOM DIMSE C-STORE
  -> Orthanc reference target
```

이 단계에서 Sandbag과 Orthanc는 둘 다 `가짜 PACS`처럼 보입니다. 차이는 Sandbag은 우리가 실패 케이스와 oracle을 제어하는 target이고, Orthanc는 실제 제품에 가까운 reference target이라는 점입니다.

## DICOMweb까지 붙였을 때

```text
Viewer / AI client / Archon
  -> QIDO-RS: study/series/instance 검색
  -> WADO-RS: image/metadata 조회
  -> STOW-RS: image/object 저장
  -> Sandbag 또는 Orthanc
```

DICOMweb에서 Sandbag 또는 Orthanc는 HTTP 기반 의료영상 archive server 역할을 합니다. FHIR처럼 HTTP endpoint를 때리는 구조가 가능하지만, 리소스가 `Patient` 같은 병원정보가 아니라 `Study`, `Series`, `Instance`, DICOM metadata, pixel data라는 점이 다릅니다.

## Orthanc의 정확한 위치

Orthanc는 Sandbag 자체가 아닙니다.

```text
Sandbag
  우리가 만드는 최소/통제형 DICOM target
  fuzzing, deterministic oracle, 실패 케이스 재현 중심

Orthanc
  이미 존재하는 오픈소스 mini-PACS
  실제형 정상 동작, DICOMweb plugin, REST 관리 API, 호환성 비교 중심
```

따라서 구현 계획에서는 `Sandbag target`과 `Orthanc reference target`을 나란히 둡니다. HAPI FHIR가 FHIR reference server였던 것처럼 Orthanc는 DICOM reference server에 가깝습니다. 다만 DICOM에서는 그 reference server의 의미가 병원정보서버가 아니라 의료영상 저장소, 즉 PACS/VNA입니다.

## MVP 표현

문서와 티켓에서는 아래처럼 표현합니다.

```text
DICOM protocol MVP:
  Sandbag acts as a fake PACS/VNA target.
  Orthanc is used as a reference mini-PACS target.
  Archon acts as a DICOM SCU/requester.

Phase 1:
  C-ECHO to verify DICOM AE connectivity.
  C-STORE to send synthetic DICOM instances.

Phase 1.5:
  QIDO-RS to search studies/series/instances.
  WADO-RS to retrieve metadata or objects.
  STOW-RS to store objects over HTTP.
```
