# DICOM protocol selection research

작성일: 2026-06-08

## 결론

DICOM 추가 MVP는 `parser MVP`가 아니라 `protocol addition MVP`입니다.

가장 많이 마주칠 표준 표면은 classic DICOM network, 즉 DIMSE over TCP/IP입니다. 특히 `C-ECHO`와 `C-STORE`가 1차 MVP에 가장 적합합니다. 병원 장비와 PACS의 기본 흐름은 modality가 DICOM instance를 PACS/archive/workstation으로 보내는 구조이고, DICOM PS3.4 Storage Service도 이 용도를 직접 설명합니다.

DICOMweb은 DIMSE를 대체하는 단일 표준이라기보다 modern enterprise/cloud/web API 표면입니다. QIDO-RS, WADO-RS, STOW-RS는 viewer, cloud PACS/VNA, AI/analytics 연계에서 중요하고, 공식 DICOMweb 설명도 DICOMweb이 직접 구현되거나 DIMSE proxy로 구현될 수 있다고 설명합니다.

따라서 ArchonZ-Sandbag의 DICOM MVP는 다음 순서가 맞습니다.

| 단계 | 범위 | 이유 |
|---|---|---|
| 1 | DIMSE `C-ECHO` Verification SCP | DICOM AE 연결성의 최소 protocol oracle |
| 1 | DIMSE `C-STORE` Storage SCP | enterprise imaging에서 가장 흔한 image/object ingest 흐름 |
| 1 | PS3.10 file 생성/검증 | protocol payload와 fuzz seed를 만들기 위한 하부 기반 |
| 1.5 | DICOMweb Studies Service subset: QIDO-RS, WADO-RS metadata/retrieve, STOW-RS | HTTP 기반 검증/퍼징, cloud/web enterprise 연계 |
| 2 | C-FIND/C-MOVE, MWL, Storage Commitment, MPPS | PACS/RIS/modalities workflow까지 확장 |

## 근거 요약

| 질문 | 판단 | 근거 |
|---|---|---|
| DICOM은 어떤 버전으로 잡나? | `DICOM Current Edition 2026b`를 evidence snapshot으로 사용한다. | 공식 current directory가 2026b bulk zip/pdf/html/source를 제공한다. DICOM conformance는 edition명보다 SOP Class, Web Service, Transfer Syntax, role 단위로 표현한다. |
| 가장 잘 쓰이는 것은? | 장비/PACS installed base에서는 DIMSE Storage `C-STORE`, Verification `C-ECHO`, Query/Retrieve `C-FIND/C-MOVE`, MWL이 중심이다. | PS3.4 Storage/Verification, PS3.7 DIMSE, PS3.8 TCP/IP, IHE SWF, vendor conformance statements. |
| 기업 표준은? | 단일 API 하나가 아니라 DICOM Conformance Statement + IHE workflow profile 조합으로 봐야 한다. | Siemens/AGFA/GE/Sectra/Philips 모두 제품별 conformance statement를 공개하고, IHE SWF는 HL7 기반 RIS/HIS와 DICOM 기반 modality/PACS를 잇는다. |
| DICOMweb은 어디에 놓나? | modern enterprise API surface. Cloud/VNA/viewer/AI 연계에는 QIDO-RS/WADO-RS/STOW-RS가 중요하다. | PS3.18, DICOMweb overview, Google Cloud Healthcare API, AGFA/GE/Sectra conformance statements. |

## 공식 표준 근거

| 출처 | 확인 내용 |
|---|---|
| [DICOM Current Edition](https://www.dicomstandard.org/current/) | DICOM 표준은 MITA/NEMA가 관리하고, Part 1-22가 PDF/HTML/CHTML/DOCX/ODT/XML로 제공된다. |
| [DICOM official current directory](https://dicom.nema.org/medical/dicom/current/) | 2026-03-27 게시된 `DocBookDICOM2026b_*` zip/tar와 output/source 디렉터리가 공개되어 있다. |
| [PS3.7 Message Exchange](https://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_1.html) | DIMSE는 peer DICOM Application Entity 간 medical images와 related information을 교환하기 위한 service/protocol이다. |
| [PS3.8 TCP/IP](https://dicom.nema.org/medical/dicom/current/output/chtml/part08/chapter_9.html) | DICOM Upper Layer Protocol은 TCP/IP transport와 함께 사용되고, port 104 또는 11112가 권장된다. |
| [PS3.4 Verification](https://dicom.nema.org/medical/dicom/current/output/chtml/part04/chapter_A.html) | Verification Service는 peer DICOM AE 간 application-level communication을 `C-ECHO DIMSE-C`로 검증한다. |
| [PS3.4 Storage](https://dicom.nema.org/medical/dicom/current/output/chtml/part04/chapter_B.html) | Storage Service는 images, waveforms, reports 등을 다른 DICOM AE로 보내는 class-of-service이고 `C-STORE DIMSE-C`를 사용한다. |
| [PS3.18 Web Services](https://dicom.nema.org/medical/dicom/current/output/chtml/part18/chapter_1.html) | PS3.18은 HTTP family 기반 web services를 정의하며, RESTful Web Services를 DICOMweb이라고 부른다. |
| [DICOMweb overview](https://www.dicomstandard.org/using/dicomweb) | DICOMweb은 web-based medical imaging용 RESTful service set이며, 직접 구현하거나 DIMSE service의 proxy로 구현될 수 있다. |

## Enterprise evidence

이번 리서치에서 받은 enterprise conformance artifact:

```text
docs/dicom/raw/enterprise/
  agfa-enterprise-imaging-8.4.x-dicom-conformance.pdf
  agfa-enterprise-imaging-8.4.x-dicom-conformance.txt
  ge-enterprise-archive-8-dicom-conformance.pdf
  ge-enterprise-archive-8-dicom-conformance.txt
  sectra-pacs-uniview-24.1-dicom-conformance.pdf
  sectra-pacs-uniview-24.1-dicom-conformance.txt
```

| 제품/출처 | DIMSE evidence | DICOMweb evidence |
|---|---|---|
| [AGFA DICOM Conformance](https://www.agfahealthcare.com/dicom-conformance/) / Enterprise Imaging 8.4.x | Verification, Storage, Storage Commitment, Query/Retrieve, Modality Worklist, MPPS를 SCU/SCP로 언급한다. | RESTful DICOMweb AE가 WADO-RS/QIDO-RS를 지원하고 STOW-RS는 WIP로 언급된다. |
| [GE Enterprise Archive 8 conformance](https://www.gehealthcare.com/-/jssmedia/documents/us-global/products/interoperability/dicom/radiology-pacs-ris/enterprise-archive-80-direction--doc2512664-rev-4.pdf?hash=6F78F6B6E18B53B5FCC5B3C7A01CDA73&rev=-1) | Storage Commitment, MWL, C-FIND/C-MOVE, C-STORE 관련 archive 흐름을 다룬다. | WADO-RS, QIDO-RS, STOW-RS specification 섹션이 있다. |
| [Sectra PACS/UniView conformance](https://medical.sectra.com/wp-content/uploads/sites/3/2022/04/conformance-statement-24-1.pdf) | PACS Core가 Storage SCP/SCU, Q/R SCP/SCU, MWL SCP, Storage Commitment를 제공한다. | WADO-RS, QIDO-RS, STOW-RS provider/user application을 별도로 제공한다. |
| [Siemens Healthineers DICOM](https://www.siemens-healthineers.com/services/it-standards/dicom) | DICOM이 acquisition devices/modalities, diagnostic workstations, PACS, archive, RIS/CIS, RT planning 사이의 connectivity/exchange를 가능하게 한다고 설명한다. | 제품별 conformance statement 공개 체계를 제공한다. |
| [Philips CT conformance page](https://www.usa.philips.com/healthcare/support/dicom/computed-tomography-dicom-conformance-statements) | modality별 DICOM conformance statement를 장기간 공개한다. | modality/vendor별 conformance가 enterprise 구매/연동 기준임을 보여준다. |
| [Google Cloud Healthcare API DICOM conformance](https://docs.cloud.google.com/healthcare-api/docs/dicom) | DIMSE C-Store 등은 adapters로 연결한다고 설명한다. | DICOM store가 PS3.18 DICOMweb Studies Service/Resources, 즉 WADO-RS/STOW-RS/QIDO-RS subset을 지원한다고 명시한다. |
| [IHE Scheduled Workflow](https://wiki.ihe.net/index.php/Scheduled_Workflow) | HL7 기반 RIS/HIS와 DICOM 기반 modality/PACS 사이를 잇고, MWL, Storage Commitment, MPPS를 사용한다. | enterprise workflow 기준은 DICOM 단독보다 IHE profile과 함께 보는 것이 맞다. |

## ArchonZ-Sandbag implementation position

1차 DICOM protocol addition은 `DIMSE C-ECHO + C-STORE SCP`를 먼저 구현하는 것이 맞습니다. 이 조합은 DICOM AE, association, presentation context, transfer syntax, SOP Class UID, DIMSE status를 모두 건드리므로 "프로토콜을 추가했다"는 의미가 분명합니다.

동시에 `pydicom`은 parser MVP의 주인공이 아니라 payload factory/oracle입니다. Synthetic DICOM instance를 만들고, C-STORE로 받은 파일을 PS3.10/PS3.5/PS3.6 기준으로 확인하며, DICOMweb 응답용 metadata를 만드는 데 사용합니다.

DICOMweb은 1차 후반 또는 1.5차에서 붙입니다. 이유는 FHIR처럼 HTTP 테스트/퍼징을 재사용하기 쉽고 cloud/vendor API와 맞지만, 병원 장비/PACS installed base의 핵심인 DIMSE를 생략하면 enterprise DICOM protocol MVP라고 보기 어렵기 때문입니다.

## Recommended conformance wording

문서와 테스트 이름에는 `DICOM 2026b parser`처럼 쓰지 않습니다.

대신 아래처럼 씁니다.

```text
DICOM evidence snapshot: Current Edition 2026b
Supported DIMSE roles:
  Verification SOP Class SCP
  Storage SOP Class SCP for Secondary Capture Image Storage and CT Image Storage
Supported transfer syntaxes:
  Explicit VR Little Endian
  Implicit VR Little Endian
Supported DICOMweb roles:
  Studies Web Service Origin Server subset: QIDO-RS, WADO-RS metadata/retrieve, STOW-RS store
Payload/file support:
  PS3.10 DICOM File Format, metadata-first parsing, synthetic de-identified samples only
```
