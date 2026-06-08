# DICOM 표준/버전 리서치

작성일: 2026-06-08

## 결론

DICOM은 FHIR처럼 `R4` 또는 `R5` 같은 구현 버전을 고르는 구조가 아닙니다. DICOM 표준은 계속 보수되는 multi-part 표준이고, conformance는 특정 edition이 아니라 SOP Class, Web Service, Media Storage Application Profile, Transfer Syntax 같은 feature identifier를 기준으로 주장합니다.

따라서 ArchonZ-Sandbag의 DICOM MVP 기준은 다음처럼 잡습니다.

```text
Evidence snapshot: DICOM Current Edition 2026b
Implementation target: PS3.7/PS3.8 DIMSE subset + PS3.18 DICOMweb + PS3.10 file payload support
Conformance wording: "DICOM 2026b" 단독 버전이 아니라 지원 SOP Class/서비스/역할을 명시
```

초기 구현에서 "DICOM 버전"이라고 부를 값은 `2026b evidence snapshot`입니다. 실제 프로토콜 호환성 설명에서는 `DICOM CT Image Storage SOP Class`, `Verification SOP Class`, `DICOM WADO-RS/STOW-RS/QIDO-RS`, `Explicit VR Little Endian Transfer Syntax`처럼 단위 기능을 써야 합니다.

프로토콜 선택과 enterprise 근거는 [protocol-selection-research.md](protocol-selection-research.md)에 분리했습니다.

## 공식 표준 근거

| 근거 | 확인 내용 |
|---|---|
| DICOM Current Edition | 현재 링크는 `current` 경로로 제공되고, 2026-03-27 게시된 `2026b` 아카이브와 output 디렉터리가 열려 있음 |
| PS3.1 Introduction | 표준은 continuous maintenance 방식이고, approved Final Text가 즉시 효력을 가짐 |
| PS3.1 Referencing | conformance requirement/claim은 표준 edition이 아니라 feature name/identifier를 참조해야 함 |
| PS3.10 | DICOM file은 128-byte preamble, 4-byte `DICM` prefix, File Meta Information, Transfer Syntax UID를 핵심으로 함 |
| PS3.18 | DICOMweb은 HTTP family 기반 Web Services이며 WADO-RS/STOW-RS/QIDO-RS를 포함함 |
| PS3.7/PS3.8 | classic DICOM network는 DIMSE message exchange와 Upper Layer Protocol over TCP/IP를 사용함 |

## 다운로드한 원문

이번 리서치에서 우선 구현 판단에 필요한 표준 파트를 원문 PDF/HTML로 받았습니다.

```text
docs/dicom/raw/2026b/pdf/
docs/dicom/raw/2026b/html/
```

다운로드 완료:

| 파일 | 이유 |
|---|---|
| `part01.pdf`, `part01.html` | 표준 구조, maintenance, conformance/version 참조 방식 |
| `part02.pdf`, `part02.html` | Conformance Statement 작성 기준 |
| `part03.pdf`, `part03.html` | IOD, CT/MR/Secondary Capture 등 객체 정의 |
| `part04.pdf`, `part04.html` | Storage, Query/Retrieve, Verification service classes |
| `part05.pdf`, `part05.html` | Data Set, VR/VM, Transfer Syntax, encoding |
| `part06.pdf`, `part06.html` | Data Dictionary, UID registry |
| `part07.pdf`, `part07.html` | DIMSE message exchange, C-STORE/C-FIND/C-ECHO |
| `part08.pdf`, `part08.html` | DICOM Upper Layer Protocol over TCP/IP |
| `part10.pdf`, `part10.html` | DICOM file format and media storage |
| `part18.pdf`, `part18.html` | DICOMweb HTTP services |
| `releasenotes_2026b.pdf` | 2026b 변경점 확인 |

## 다운로드한 enterprise conformance 문서

표준 문서만으로는 "기업에서 실제로 무엇을 쓰는지"를 판단하기 어렵기 때문에 PACS/VNA/enterprise imaging 제품의 DICOM Conformance Statement도 받았습니다.

```text
docs/dicom/raw/enterprise/
```

| 파일 | 이유 |
|---|---|
| `agfa-enterprise-imaging-8.4.x-dicom-conformance.pdf`, `.txt` | Enterprise Imaging의 DIMSE, DICOMweb, MWL, MPPS, Storage Commitment 지원 확인 |
| `ge-enterprise-archive-8-dicom-conformance.pdf`, `.txt` | Enterprise Archive의 WADO-RS/QIDO-RS/STOW-RS와 archive DIMSE 흐름 확인 |
| `sectra-pacs-uniview-24.1-dicom-conformance.pdf`, `.txt` | PACS/Core/UniView의 Storage, Q/R, MWL, WADO-RS/QIDO-RS/STOW-RS 지원 확인 |

## 공식 벌크 아카이브 다운로드

공식 current 디렉터리의 2026b 벌크 아카이브도 전부 내려받았습니다. ZIP은 entry count 확인까지 했고, `tar.bz2`는 Python `tarfile`로 열리는 것을 확인했습니다. 개별 PDF/HTML은 빠른 참조용이고, 아래 bulk artifact는 원문 보존, 전체 grep, DocBook 기반 Markdown 변환에 씁니다.

저장 위치:

```text
docs/dicom/artifacts/2026b/
```

| 아카이브 | 용량 | 용도 |
|---|---:|---|
| `DocBookDICOM2026b_release_chtml_20260327091344.zip` | 98,491,288 | chunked HTML 전체 |
| `DocBookDICOM2026b_release_docbook_20260327091344.zip` | 59,589,430 | DocBook XML 전체, Markdown 변환/기계 파싱에 유리 |
| `DocBookDICOM2026b_release_docbook_changes_20260327091344.zip` | 16,216,317 | changes DocBook |
| `DocBookDICOM2026b_release_docx_20260327091344.zip` | 126,409,293 | Word 원문 |
| `DocBookDICOM2026b_release_html_20260327091344.zip` | 96,012,097 | single-page HTML 전체 |
| `DocBookDICOM2026b_release_odt_20260327091344.zip` | 63,556,630 | ODT 원문 |
| `DocBookDICOM2026b_release_pdf_20260327091344.zip` | 189,557,401 | PDF 전체 |
| `DocBookDICOM2026b_release_pdf_changes_20260327091344.zip` | 189,511,315 | PDF changes 전체 |
| `DocBookDICOM2026b_sourceandrenderingpipeline_20260327091442.tar.bz2` | 132,089,797 | source/rendering pipeline |

권장 산출 위치:

```text
docs/dicom/derived/2026b/md/
docs/dicom/derived/2026b/text/
```

## MD화 전략

이 환경에는 `pdftotext`와 `pandoc`가 있습니다.

| 입력 | 변환 전략 | 비고 |
|---|---|---|
| HTML | `pandoc -f html -t gfm` | 표/링크 유지가 비교적 좋음 |
| PDF | `pdftotext -layout` | 페이지 기반 원문 확인과 grep에 좋음 |
| DocBook XML | XML parser 또는 pandoc | 전체 표준을 구조화하기 가장 좋음 |

1차 MD화 대상:

1. `part01`: version/conformance 근거
2. `part10`: file parser/fuzzer 근거
3. `part18`: DICOMweb endpoint/HTTP 근거
4. `part07`, `part08`: DIMSE/TCP 2차 근거
5. `part05`, `part06`: VR/VM/Data Dictionary/Transfer Syntax 근거

## MVP 버전 결정

### 채택

`DICOM Current Edition 2026b`를 분석 기준으로 채택합니다.

이유:

- 공식 `current` 경로가 2026b로 공개되어 있음.
- DICOM 표준은 continuous maintenance이며 최신 consolidated edition을 쓰는 것이 신규 구현에 맞음.
- conformance는 edition이 아니라 SOP Class/서비스/UID 기준이라, `2026b`는 구현 버전이 아니라 근거 스냅샷으로 쓰는 것이 정확함.
- retired feature가 필요할 때만 과거 edition을 따로 참조하면 됨.

### 배제

`DICOM 3.0`을 구현 버전명으로 쓰는 것은 피합니다.

이유:

- 1993년에 ACR-NEMA 300을 대체하며 DICOM으로 재정립된 역사적 표현으로는 자주 쓰이지만, 신규 구현 범위를 정할 때 `DICOM 3.0 parser`처럼 쓰면 구체성이 떨어짐.
- 실제 구현/검증은 SOP Class UID, Transfer Syntax UID, DIMSE service, DICOMweb transaction 기준으로 잘라야 함.

## 1차 범위 추천

| 범위 | 표준 기준 | 이유 |
|---|---|---|
| DIMSE C-ECHO/C-STORE | PS3.7, PS3.8, PS3.4 | DICOM AE 연결성과 image/object ingest를 직접 검증하므로 protocol MVP 의미가 가장 분명함 |
| DICOMweb metadata/query/store | PS3.18 | FHIR MVP와 같은 HTTP 검증/퍼징 구조로 연결 가능하고 cloud/web enterprise 표면과 맞음 |
| DICOM file payload support | PS3.10, PS3.5, PS3.6 | parser MVP가 아니라 DIMSE/DICOMweb payload factory 및 oracle |

## 다음 확인 항목

1. 2026b release notes에서 DICOMweb/file/DIMSE 관련 변경점 추출
2. DocBook zip을 풀어서 `part05`, `part06`, `part07`, `part10`, `part18` 중심으로 Markdown 변환
3. pydicom/pynetdicom/Orthanc/DCMTK의 현재 버전과 라이선스 확인
4. synthetic DICOM sample과 공개 de-identified sample 확보
5. target conformance wording 초안 작성
6. C-FIND/C-MOVE, MWL, Storage Commitment, MPPS를 2차 protocol scope로 분리
