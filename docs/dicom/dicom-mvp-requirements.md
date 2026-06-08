# DICOM 프로토콜 추가 MVP 준비 항목

이 문서는 ArchonZ-Sandbag에 DICOM 계열 프로토콜을 추가하기 전에 필요한 자료, 도구, 구현 범위, 검증 방법을 정리합니다.

## 한 줄 결론

DICOM MVP는 parser MVP가 아니라 프로토콜 추가 MVP로 잡아야 합니다. 파일 파서는 DICOM 프로토콜을 만들고 검증하기 위한 하부 도구이고, 외부에 드러나는 1차 표면은 `DIMSE network`와 `DICOMweb`입니다.

| 계층 | 표준/기술 | Sandbag 역할 | Archon 역할 | MVP 우선순위 |
|---|---|---|---|---|
| DIMSE network | PS3.7, PS3.8, PS3.4, TCP/IP | C-ECHO/C-STORE SCP | DIMSE SCU/퍼저 | 1 |
| DICOMweb | PS3.18, HTTP | 가짜 DICOMweb archive/origin server | HTTP 클라이언트/퍼저 | 1 |
| DICOM file | PS3.10, PS3.5, PS3.6 | synthetic DICOM 생성/파싱/저장 | 파일 변이/데이터셋 oracle | 지원 계층 |

가장 작은 실전형 MVP는 `DIMSE C-ECHO + C-STORE`입니다. 여기에 FHIR처럼 HTTP 기반 검증/퍼징 구조를 붙이려면 같은 저장소를 바라보는 `DICOMweb QIDO-RS/WADO-RS/STOW-RS subset`을 같이 둡니다. `pydicom` 기반 file parser/verifier는 두 프로토콜 표면을 먹일 샘플과 oracle을 만드는 내부 기반입니다.

EVCC/FHIR와 대응되는 역할 모델은 [role-model.md](role-model.md)를 기준으로 합니다. 상세 근거와 enterprise 판단은 [protocol-selection-research.md](protocol-selection-research.md)를 기준으로 합니다.

## 필요한 표준 자료

우선 아래 DICOM 표준 파트를 기준으로 문서를 고정합니다. 현재 리서치 스냅샷은 `DICOM Current Edition 2026b`입니다. 다만 DICOM은 FHIR R4/R5처럼 구현 버전을 고르는 구조가 아니므로, 구현 설명은 edition이 아니라 SOP Class, Transfer Syntax, Web Service, DIMSE service 단위로 작성합니다.

| 표준 파트 | 쓰임 |
|---|---|
| PS3.2 Conformance | 제품/타겟이 어떤 SOP Class와 서비스 역할을 지원하는지 정리 |
| PS3.3 Information Object Definitions | CT, MR, Secondary Capture 같은 IOD 구조 확인 |
| PS3.4 Service Class Specifications | Storage, Query/Retrieve, Verification 서비스 확인 |
| PS3.5 Data Structures and Encoding | VR, VM, Transfer Syntax, Sequence, Pixel Data 인코딩 확인 |
| PS3.6 Data Dictionary | 태그 이름, VR, keyword 확인 |
| PS3.7 Message Exchange | DIMSE command/data stream, C-ECHO/C-STORE/C-FIND |
| PS3.8 Network Communication | DICOM Upper Layer Protocol over TCP/IP |
| PS3.10 Media Storage and File Format | 128-byte preamble, `DICM` prefix, File Meta Information |
| PS3.18 Web Services | DICOMweb, WADO-RS, STOW-RS, QIDO-RS |

상세 버전 판단과 원문 다운로드 상태는 [standards-research.md](standards-research.md)를 기준으로 합니다.

## 필요한 도구

| 도구 | 역할 | 비고 |
|---|---|---|
| `pydicom` | Python DICOM file parser/writer | 기본 parser 후보 |
| `pynetdicom` | Python DIMSE SCU/SCP 구현 | C-ECHO, C-STORE, C-FIND에 적합 |
| `Orthanc` | 로컬 mini-PACS/DICOM server | HAPI FHIR 같은 2차 실제 타겟 역할 |
| `DCMTK` | 기준 CLI 도구 | `dcmdump`, `echoscu`, `storescu`, `storescp` |
| `DVTk` | DICOM validation/testing 참고 | Windows GUI validation에 유용 |
| `OHIF` | DICOMweb browser viewer | DICOMweb 눈검증 |
| `Weasis` | Desktop/web DICOM viewer | 파일/네트워크 viewer 검증 |
| Rubo DICOM Parser | 헤더 확인용 GUI | core library보다는 참고용 |

## 필요한 테스트 데이터

실제 환자 DICOM은 쓰지 않는 것을 기본 원칙으로 둡니다.

1. `pydicom` example dataset 또는 synthetic dataset
2. 공개 de-identified CT/MR sample
3. `Secondary Capture`처럼 만들기 쉬운 synthetic SOP Instance
4. Pixel Data가 작은 파일, Pixel Data가 없는 metadata-only 파일
5. Transfer Syntax별 샘플: Explicit VR Little Endian, Implicit VR Little Endian, 가능하면 JPEG 계열 1개
6. DICOMDIR은 1차 필수 아님, media interchange 2차 검증 항목

## 1차 구현 후보

### DIMSE protocol sandbag

예상 파일:

- `services/dicom_dimse_service.py`
- `test_dicom_dimse_verify.py`
- `docs/dicom/dimse-sandbag-usage.md`

필수 기능:

- C-ECHO Verification SCP
- C-STORE Storage SCP
- synthetic `.dcm` 수신 및 저장
- AE Title, Presentation Context, Transfer Syntax negotiation 검증
- Status `0x0000`, refusal, timeout, abort oracle 정리

초기 파라미터:

```text
Host: 127.0.0.1
Port: 11112
CalledAET: SANDBAG
CallingAET: ARCHON
Timeout: 10000
SOPClass: Verification / CT Image Storage / Secondary Capture Image Storage
TransferSyntax: Explicit VR Little Endian, Implicit VR Little Endian
```

### DICOMweb sandbag

예상 파일:

- `services/dicomweb_service.py`
- `test_dicomweb_verify.py`
- `docs/dicom/dicomweb-sandbag-usage.md`

초기 endpoint:

```text
GET  /dicom-web/__health
GET  /dicom-web/studies
GET  /dicom-web/studies/{StudyInstanceUID}
GET  /dicom-web/studies/{StudyInstanceUID}/series
GET  /dicom-web/studies/{StudyInstanceUID}/series/{SeriesInstanceUID}/instances
GET  /dicom-web/studies/{StudyInstanceUID}/series/{SeriesInstanceUID}/instances/{SOPInstanceUID}/metadata
POST /dicom-web/studies
```

초기 응답은 완전한 PACS가 아니라 DICOM JSON metadata와 상태 코드 중심으로 잡습니다. FHIR의 `CapabilityStatement`처럼 DICOMweb에는 같은 단일 discovery endpoint가 없으므로, local health endpoint와 `/studies` query를 안정성 oracle로 둡니다.

### File parser/verifier

예상 파일:

- `services/dicom_file_service.py`
- `test_dicom_verify.py`
- `docs/dicom/examples/*.dcm`

필수 기능:

- synthetic DICOM 파일 생성
- `pydicom.dcmread(..., stop_before_pixels=True)`로 metadata-only 파싱
- File Meta Information 확인
- SOP Class UID, SOP Instance UID, Transfer Syntax UID 확인
- 주요 태그 추출: PatientID, StudyInstanceUID, SeriesInstanceUID, SOPInstanceUID, Modality
- invalid preamble, missing `DICM`, 잘못된 VR/length에 대한 오류 oracle 정리

## 2차 구현 후보

### DIMSE Query/Retrieve and workflow

초기 서비스:

| DIMSE 서비스 | Sandbag 역할 | 검증 |
|---|---|---|
| C-FIND | Query/Retrieve FIND SCP | Patient/Study level 최소 검색 |
| C-MOVE/C-GET | Query/Retrieve retrieve SCP | 저장된 synthetic instance 전송 |
| MWL C-FIND | Modality Worklist SCP | scheduled procedure 최소 검색 |
| Storage Commitment | Storage Commitment SCP | 수신 instance 보관 책임 응답 |

## Fuzzing 표면

| 영역 | 주요 변이 |
|---|---|
| File Meta | preamble, `DICM` prefix, group `0002`, Transfer Syntax UID, Implementation UID |
| Dataset encoding | VR, VM, length, undefined length, Sequence nesting, private tags |
| UID fields | Study/Series/SOP UID 형식, 너무 긴 UID, 빈 UID, 중복 UID |
| Pixel Data | 누락, 과대 길이, compressed transfer syntax 불일치 |
| DICOMweb HTTP | path UID, query parameter, Accept/Content-Type, multipart boundary, JSON metadata |
| DIMSE association | AE Title, Presentation Context, Abstract Syntax, Transfer Syntax negotiation |
| DIMSE command | C-ECHO/C-STORE/C-FIND status, identifier dataset, cancel/abort/release |

## Oracle

| 계층 | 정상 oracle | 실패 oracle |
|---|---|---|
| File parser | pydicom parse success, expected tags present | InvalidDicomError, missing required meta, controlled rejection |
| DICOMweb | HTTP 200/201/204, DICOM JSON metadata, stored instance count | 400/404/406/415, JSON error body, server liveness 유지 |
| DIMSE | Status `0x0000`, C-FIND pending `0xFF00`, association release | refused association, DIMSE failure status, timeout, abort |

## 브랜치 변경 없이 다른 브랜치에 넣는 방법

가장 안전한 방법은 `git worktree`입니다. 현재 브랜치는 그대로 두고, 같은 repo의 다른 checkout 폴더를 하나 더 만들어서 거기서 파일을 추가합니다.

새 DICOM 브랜치를 현재 FHIR 브랜치 위에 쌓을 때:

```powershell
git worktree add -b protocol/dicom-protocol-mvp C:\Users\vip\suresoft\ArchonZ-Sandbag-dicom HEAD
```

새 DICOM 브랜치를 `main`에서 따로 시작할 때:

```powershell
git worktree add -b protocol/dicom-protocol-mvp C:\Users\vip\suresoft\ArchonZ-Sandbag-dicom main
```

이미 브랜치가 있을 때:

```powershell
git worktree add C:\Users\vip\suresoft\ArchonZ-Sandbag-dicom protocol/dicom-protocol-mvp
```

그 다음에는 새 폴더에서만 작업합니다.

```powershell
cd C:\Users\vip\suresoft\ArchonZ-Sandbag-dicom
git status --short --branch
```

이렇게 하면 현재 `C:\Users\vip\suresoft\ArchonZ-Sandbag` 폴더의 `protocol/hl7-fhir-r4-mvp` 브랜치는 바뀌지 않습니다.

주의할 점:

- 같은 브랜치를 두 worktree에서 동시에 checkout할 수 없습니다.
- 새 DICOM 작업이 FHIR 구현 위에 의존하면 `HEAD`에서 브랜치를 따고, 독립 작업이면 `main`에서 따는 편이 좋습니다.
- 단순 문서만 미리 남기는 수준이면 현재 브랜치에 `docs/dicom/*`만 만들고 나중에 cherry-pick하거나 복사해도 됩니다.

## 추천 순서

1. `docs/dicom/standards-summary.md` 작성
2. `pydicom` 기반 synthetic `.dcm` 생성/파싱 verifier 작성
3. `pynetdicom` 기반 C-ECHO/C-STORE SCP 작성
4. Orthanc + DCMTK로 기준 동작 확인
5. DICOMweb sandbag 최소 endpoint 작성
6. C-FIND/C-MOVE/MWL/Storage Commitment를 2차 protocol scope로 확장
7. Archon package 파라미터와 PIT seed를 file/DICOMweb/DIMSE 계층별로 분리
